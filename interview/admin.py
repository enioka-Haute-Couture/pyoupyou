from django.contrib import admin

from interview.models import ContractType, Candidate, Document, Process, Interview, \
    SourcesCategory, Sources


@admin.register(ContractType)
class ContractTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'has_duration')
    list_filter = ('has_duration',)
    search_fields = ('name',)


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'email', 'phone')
    search_fields = ('name',)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'created_date',
        'candidate',
        'document_type',
        'content',
        'still_valid',
    )
    list_filter = ('created_date', 'candidate', 'still_valid')


@admin.register(Process)
class ProcessAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'candidate',
        'subsidiary',
        'start_date',
        'end_date',
        'contract_type',
        'salary_expectation',
        'contract_duration',
    )
    list_filter = (
        'candidate',
        'subsidiary',
        'start_date',
        'end_date',
        'contract_type',
    )


@admin.register(Interview)
class InterviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'process', 'state', 'rank', 'planned_date')
    list_filter = ('process', 'planned_date')


@admin.register(SourcesCategory)
class SourcesCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Sources)
class SourcesAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'category', 'archived')
    list_filter = ('category', 'archived')
    search_fields = ('name',)
