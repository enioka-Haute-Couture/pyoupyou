import requests
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
from rest_framework import serializers
from rest_framework.fields import empty

from interview.models import Process, Candidate, Document, Sources, Offer
from ref.models import Subsidiary


class DocumentSerializer(serializers.Serializer):
    File = serializers.URLField()
    Name = serializers.CharField()


class UrlFieldOrEmpty(serializers.URLField):
    def run_validation(self, data=empty):
        try:
            return super().run_validation(data)
        except serializers.ValidationError:
            return ""


class CognitoWebHookSerializer(serializers.Serializer):
    def create(self, validated_data):
        candidate = Candidate.objects.create(
            name=validated_data.get("Name"),
            email=validated_data.get("Email"),
            phone=validated_data.get("Phone") or "",
            linkedin_url=validated_data.get("Linkedin") or "",
        )

        Process.objects.create(
            candidate=candidate,
            sources=Sources.objects.get(id=validated_data["sources"]),
            subsidiary=Subsidiary.objects.get(id=validated_data["subsidiary"]),
            offer=Offer.objects.filter(id=validated_data["Offer_Value"]).first(),
            contract_start_date=validated_data.get("Availability"),
            other_informations=validated_data.get("Motivation") or "",
        )

        documents = validated_data.pop("Document", [])
        for document in documents:
            r = requests.get(document["File"], stream=True)
            with NamedTemporaryFile(delete=True) as file_tmp:
                file_tmp.write(r.content)
                file_tmp.flush()
                Document.objects.create(
                    document_type="CV", content=File(file=file_tmp, name=document["Name"]), candidate=candidate
                )

    # Candidate
    Name = serializers.CharField(max_length=200)
    Email = serializers.EmailField(allow_blank=True)
    Phone = serializers.CharField(max_length=20, allow_blank=True, allow_null=True, required=False)
    Linkedin = UrlFieldOrEmpty(allow_blank=True, allow_null=True, required=False)

    # Process
    sources = serializers.IntegerField(allow_null=True)
    subsidiary = serializers.IntegerField()
    Offer_Value = serializers.IntegerField(allow_null=True, required=False)
    Motivation = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    Availability = serializers.DateField(allow_null=True, required=False)

    Document = DocumentSerializer(many=True, required=False)
