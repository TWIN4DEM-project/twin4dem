from django.db import transaction
from rest_framework import serializers


class BatchListSerializer(serializers.ListSerializer):
    @transaction.atomic
    def create(self, validated_data):
        items = []
        for index, attrs in enumerate(validated_data):
            try:
                items.append(self.child.create(attrs))
            except serializers.ValidationError as e:
                errors = [{} for _ in validated_data]
                errors[index] = e.detail
                raise serializers.ValidationError(errors)
        return items
