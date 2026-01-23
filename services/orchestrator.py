import json
from sqlmodel import Session, select, desc
from database import SearchSession, ChatSession, ChatMessage, ExtractionSchema
from llm_engine import conduct_interview, generate_schema_proposal, check_confirmation

class DeepResearchOrchestrator:
    def __init__(self, session: Session):
        self.db = session

    async def handle_message(self, chat_history: list, user_content: str):
        search_session = self._get_or_create_search_session(user_content)
        print(f"[DEBUG ORCH] Session #{search_session.id} Stage: {search_session.stage}")
        
        chat_session = self._get_or_create_chat_session(search_session.id)
        self._save_message(chat_session.id, "user", user_content, {"stage": search_session.stage})

        # Проверка подтверждения схемы
        if search_session.stage == "schema_agreement":
            if await check_confirmation(user_content):
                await self.confirm_schema(search_session.id, search_session.schema_agreed or "{}")
                return {"type": "schema_confirmed", "message": "Схема подтверждена! Начинаю сбор данных...", "search_id": search_session.id, "stage": "parsing"}

        # Логика интервью
        if search_session.stage == "interview":
            idata = search_session.interview_data or ""
            # ВАЖНО: передаем накопленные данные
            res = await conduct_interview(chat_history, idata)
            
            # Накапливаем контекст "вопрос-ответ"
            new_idata = (idata + f"\nUser: {user_content}\nAI: {res['response']}").strip()[-2000:] # Ограничим длину
            search_session.interview_data = new_idata
            
            resp = {"type": "interview", "message": res["response"], "stage": search_session.stage, "search_id": search_session.id}

            if not res.get("needs_more_info", True):
                print("[DEBUG ORCH] Interview complete!")
                search_session.stage = "schema_agreement"
                
                # Приводим критерии к строке
                crit = res.get("criteria_summary", search_session.query_text)
                if isinstance(crit, dict): crit = json.dumps(crit, ensure_ascii=False)
                search_session.query_text = crit
                
                s_res = await generate_schema_proposal(crit)
                search_session.schema_agreed = json.dumps(s_res["schema"], ensure_ascii=False)
                
                resp.update({"stage": "schema_agreement", "criteria_summary": crit, "schema_proposal": search_session.schema_agreed})

            self.db.add(search_session); self.db.commit()
            return resp
        
        return {"type": "info", "message": f"Ожидание... (Стадия: {search_session.stage})"}

    def _get_or_create_search_session(self, query: str) -> SearchSession:
        s = self.db.exec(select(SearchSession).where(SearchSession.mode == "deep", SearchSession.status == "created").order_by(desc(SearchSession.created_at))).first()
        if not s:
            print("[DEBUG ORCH] Creating new Deep Session")
            s = SearchSession(query_text=query, mode="deep", stage="interview", status="created", limit_count=10)
            self.db.add(s); self.db.commit(); self.db.refresh(s)
        return s

    def _get_or_create_chat_session(self, search_id: int) -> ChatSession:
        title = f"Deep Research Chat - {search_id}"
        c = self.db.exec(select(ChatSession).where(ChatSession.title.contains(str(search_id)))).first()
        if not c:
            c = ChatSession(title=title)
            self.db.add(c); self.db.commit(); self.db.refresh(c)
        return c

    def _save_message(self, chat_id: int, role: str, content: str, meta: dict):
        msg = ChatMessage(role=role, content=content, chat_session_id=chat_id, extra_metadata=json.dumps(meta, ensure_ascii=False))
        self.db.add(msg); self.db.commit()

    async def confirm_schema(self, search_id: int, schema_str: str):
        print(f"[DEBUG ORCH] Confirming schema for Task #{search_id}")
        s = self.db.get(SearchSession, search_id)
        if not s: return None
        s.schema_agreed, s.stage, s.status = schema_str, "parsing", "confirmed"
        
        name = f"DeepResearch_{s.id}"
        ex = self.db.exec(select(ExtractionSchema).where(ExtractionSchema.name == name)).first()
        if not ex:
            ex = ExtractionSchema(name=name, description="Auto", structure_json=schema_str)
            self.db.add(ex); self.db.commit(); self.db.refresh(ex)
        s.schema_id = ex.id
        self.db.add(s); self.db.commit()