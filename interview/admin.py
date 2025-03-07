from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html


from interview.models import (
    ContractType,
    Candidate,
    Document,
    Process,
    Interview,
    SourcesCategory,
    Sources,
    Offer,
    InterviewKind,
    ResponsibleRule,
)


@admin.register(ContractType)
class ContractTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "has_duration")
    list_filter = ("has_duration",)
    search_fields = ("name",)


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "email", "phone")
    search_fields = ("name",)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "created_date", "candidate", "document_type", "content", "still_valid")
    list_filter = ("created_date", "still_valid", "document_type")
    search_fields = ("candidate__name",)


@admin.register(Process)
class ProcessAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "candidate",
        "subsidiary",
        "sources",
        "start_date",
        "end_date",
        "contract_type",
        "salary_expectation",
        "contract_duration",
        "state",
    )
    list_filter = ("subsidiary", "start_date", "end_date", "contract_type", "state", "sources")
    search_fields = ("candidate__name",)


@admin.register(Interview)
class InterviewAdmin(admin.ModelAdmin):
    list_display = ("id", "process", "state", "rank", "planned_date")
    list_filter = ("process__subsidiary", "planned_date", "state")
    search_fields = ("process__candidate__name",)


@admin.register(SourcesCategory)
class SourcesCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Sources)
class SourcesAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "archived", "processes_list_url")
    list_filter = ("category", "archived")
    search_fields = ("name",)

    def processes_list_url(self, obj):
        return format_html("<a href='{url}'>🔗</a>", url=reverse("process-list-source", args=[str(obj.id)]))

    processes_list_url.short_description = "URL"


@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "subsidiary", "archived", "processes_list_url")
    list_filter = ("subsidiary", "archived")
    search_fields = ("name",)

    def processes_list_url(self, obj):
        return format_html("<a href='{url}'>🔗</a>", url=reverse("process-list-offer", args=[str(obj.id)]))

    processes_list_url.short_description = "URL"


@admin.register(InterviewKind)
class InterviewKindAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(ResponsibleRule)
class ResponsibleRuleAdmin(admin.ModelAdmin):
    list_display = ("id", "responsible", "subsidiary", "contract_type", "sources", "offer")
    search_fields = ("name",)
