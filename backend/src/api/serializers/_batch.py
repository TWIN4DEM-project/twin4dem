from django.db import transaction
from rest_framework import serializers


class BatchListSerializer(serializers.ListSerializer):
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
