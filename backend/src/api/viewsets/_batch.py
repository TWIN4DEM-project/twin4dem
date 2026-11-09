class BatchCreateMixin:

    def get_serializer(self, *args, **kwargs):
        if self.action == "create" and isinstance(kwargs.get("data"), list):
            kwargs.update(many=True, allow_empty=False)
        return super().get_serializer(*args, **kwargs)
