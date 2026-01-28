from rest_framework import serializers
from .models import CustomUser
from irrbb_app.models import Banco


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ("id", "username", "email", "birth_date", "bank_name", "password")
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        return CustomUser.objects.create_user(**validated_data)

class BankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banco
        fields = ('id', 'nombre')

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
