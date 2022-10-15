from django.db import models
from django_dataclass_models import TypedModel

# Create your models here.


class OriginalAbstractModel(models.Model):
    class Meta:  # type:ignore
        abstract = True  # type:ignore


class TypedAbstractModel(TypedModel, abstract=True):
    pass


class OriginalModel(models.Model):
    char = models.CharField(max_length=255)
    char_or_null = models.CharField(max_length=255, null=True)
    char_with_default = models.CharField(max_length=255, default="hello")
    number = models.IntegerField()


class ExampleTypedModel(TypedModel):
    char: str
    char_or_null: str | None
    char_with_default: str = "hello"
    number: int
