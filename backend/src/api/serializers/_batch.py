from django.db import transaction
from rest_framework import serializers


class BatchListSerializer(serializers.ListSerializer):
    def run_child_validation(self, data):
        self.child.initial_data = data
        return super().run_child_validation(data)

    @transaction.atomic
    def create(self, validated_data):
        items, errors = [], []
        for attrs in validated_data:
            try:
                items.append(self.child.create(attrs))
            except serializers.ValidationError as e:
                errors.append(e.detail)
            else:
                errors.append({})
        if any(errors):
            raise serializers.ValidationError(errors)
        return items
