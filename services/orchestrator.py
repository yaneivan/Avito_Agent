import json
from sqlmodel import Session, select, desc
from database import SearchSession, ChatSession, ChatMessage, ExtractionSchema
from llm_engine import conduct_interview, generate_schema_proposal

class DeepResearchOrchestrator:
    def __init__(self, session: Session):
        self.db = session

    async def handle_message(self, chat_history: list, user_content: str):
        search_session = self._get_or_create_search_session(user_content)
        chat_session = self._get_or_create_chat_session(search_session.id)
        
        self._save_message(chat_session.id, "user", user_content, {"stage": search_session.stage})

        if search_session.stage == "interview" or search_session.stage == "schema_agreement":
             if self._detect_schema_confirmation(user_content):
                 await self.confirm_schema(search_session.id, search_session.schema_agreed or "{}")
                 return {
                    "type": "schema_confirmed",
                    "message": "Схема подтверждена! Начинаю сбор данных...",
                    "search_id": search_session.id,
                    "stage": "parsing"
                 }

        if search_session.stage == "interview":
            res = await self._process_interview(search_session, chat_history)
            if res.get("stage") == "schema_agreement" and res.get("criteria_summary"):
                search_session.query_text = res["criteria_summary"]
                self.db.add(search_session)
                self.db.commit()
            return res
        
        return {"type": "info", "message": "Стадия: " + search_session.stage}

    def _get_or_create_search_session(self, query: str) -> SearchSession:
        session = self.db.exec(
            select(SearchSession).where(
                SearchSession.mode == "deep",
                SearchSession.status == "created"
            ).order_by(desc(SearchSession.created_at))
        ).first()

        if not session:
            session = SearchSession(
                query_text=query, mode="deep", stage="interview", 
                status="created", limit_count=10
            )
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
        return session

    def _get_or_create_chat_session(self, search_id: int) -> ChatSession:
        title = f"Deep Research Chat - {search_id}"
        chat = self.db.exec(select(ChatSession).where(ChatSession.title.contains(str(search_id)))).first()
        if not chat:
            chat = ChatSession(title=title)
            self.db.add(chat)
            self.db.commit()
            self.db.refresh(chat)
        return chat

    def _save_message(self, chat_id: int, role: str, content: str, meta: dict):
        msg = ChatMessage(
            role=role, content=content, chat_session_id=chat_id,
            extra_metadata=json.dumps(meta, ensure_ascii=False)
        )
        self.db.add(msg)
        self.db.commit()

    def _detect_schema_confirmation(self, user_input: str) -> bool:
        user_input_lower = user_input.lower().strip()
        confirmation_keywords = ['да', 'верно', 'согласен', 'ok', 'okay', 'подтверждаю', 'давай', 'поехали', 'идем дальше']
        modification_keywords = ['нет', 'измени', 'поменяй', 'не то', 'добавь', 'убери']
        has_confirm = any(k in user_input_lower for k in confirmation_keywords)
        has_modify = any(k in user_input_lower for k in modification_keywords)
        return has_confirm and not has_modify

    async def _process_interview(self, session: SearchSession, history: list):
        try:
            result = await conduct_interview(history)
            idata = json.loads(session.interview_data) if session.interview_data else {}
            idata[len(idata)] = {"q": history[-1]['content'], "a": result.get("response")}
            session.interview_data = json.dumps(idata, ensure_ascii=False)

            resp = {
                "type": "interview", 
                "message": result.get("response"), 
                "stage": session.stage, 
                "search_id": session.id
            }

            if not result.get("needs_more_info", True):
                session.stage = "schema_agreement"
                crit = result.get("criteria_summary", session.query_text)
                s_res = await generate_schema_proposal(crit)
                session.schema_agreed = s_res["schema"]
                resp["stage"] = "schema_agreement"
                resp["criteria_summary"] = crit
                resp["schema_proposal"] = s_res["schema"]

            self.db.add(session)
            self.db.commit()
            return resp
        except Exception as e:
            return {"type": "error", "message": f"Ошибка LLM: {str(e)}"}

    async def confirm_schema(self, search_id: int, schema_str: str):
        session = self.db.get(SearchSession, search_id)
        if not session: return None
        session.schema_agreed = schema_str
        session.stage = "parsing"
        session.status = "confirmed"
        
        schema_name = f"DeepResearch_{session.id}"
        ex_schema = self.db.exec(select(ExtractionSchema).where(ExtractionSchema.name == schema_name)).first()
        if not ex_schema:
            ex_schema = ExtractionSchema(
                name=schema_name, 
                description="Auto-generated", 
                structure_json=schema_str
            )
            self.db.add(ex_schema)
            self.db.commit()
            self.db.refresh(ex_schema)
        
        session.schema_id = ex_schema.id
        self.db.add(session)
        self.db.commit()
        return {"status": "success"}