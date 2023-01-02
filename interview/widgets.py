from django import forms


class UploadFilesWidget(forms.ClearableFileInput):
    template_name = "interview/upload_file_template.html"
