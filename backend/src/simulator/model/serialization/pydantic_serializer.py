import json
from pydantic import BaseModel
from typing import Any, Dict, Type
from ..config import GovernmentConfig, MinisterConfig


MODEL_REGISTRY: Dict[str, Type[BaseModel]] = {
    "GovernmentConfig": GovernmentConfig,
    "MinisterConfig": MinisterConfig,
}

class PydanticSerializer(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, BaseModel):
            # Wrap the model with a tag to reconstruct later
            return {
                "__pydantic_model__": obj.__class__.__name__,
                "data": obj.model_dump(),
            }
        return super().default(obj)

def pydantic_decoder(obj):
    model_name = obj.get("__pydantic_model__")
    if model_name and model_name in MODEL_REGISTRY:
        model_cls = MODEL_REGISTRY[model_name]
        data = obj.get("data", {})
        return model_cls.model_validate(data)
    return obj


# Encoder function
def pydantic_dumps(obj):
    return json.dumps(obj, cls=PydanticSerializer)

# Decoder function
def pydantic_loads(obj):
    return json.loads(obj, object_hook=pydantic_decoder)
