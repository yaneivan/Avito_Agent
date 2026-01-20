from typing import Dict, Any, Type, Optional
import json
from pydantic import BaseModel, Field, create_model

class SchemaFactory:
    """
    Генерирует Pydantic-модели на лету на основе JSON-конфига.
    """
    
    @staticmethod
    def create_pydantic_model(model_name: str, schema_def: Any) -> Type[BaseModel]:
        # ФИКС: Если пришла строка, парсим её
        if isinstance(schema_def, str):
            try:
                schema_def = json.loads(schema_def)
            except:
                # Если это не JSON, возвращаем пустую модель
                return create_model(model_name)

        if not isinstance(schema_def, dict):
            return create_model(model_name)

        fields = {}
        
        for field_name, meta in schema_def.items():
            # Защита от кривой структуры (если meta это строка)
            if not isinstance(meta, dict):
                continue
                
            field_type_str = meta.get("type", "str")
            description = meta.get("desc", "")
            
            if field_type_str == "int":
                py_type = int
            elif field_type_str == "float":
                py_type = float
            elif field_type_str == "bool":
                py_type = bool
            else:
                py_type = str
            
            fields[field_name] = (Optional[py_type], Field(default=None, description=description))
            
        return create_model(model_name, **fields)