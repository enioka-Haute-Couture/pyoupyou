DEBUG = False
HAS_DDT = False

# ManifestStaticFilesStorage adds MD5 hash to filenames for cache busting
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
}
