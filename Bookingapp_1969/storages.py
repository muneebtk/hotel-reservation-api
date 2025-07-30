# static file storage
from storages.backends.s3boto3 import S3Boto3Storage

class StaticS3Boto3Storage(S3Boto3Storage):
    location = 'static'
    file_overwrite = False


# media file storage
class MediaStorage(S3Boto3Storage):
    location = 'media'
    file_overwrite = False
