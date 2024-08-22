import os
import pytest
import importlib.util
from django.contrib.auth import get_user_model
from django.utils import translation
from django.conf import settings

User = get_user_model()


@pytest.mark.order(1)
def test_modeltranslation_installed():
    loader = importlib.util.find_spec('modeltranslation')
    assert loader is not None, "modeltranslation package is not installed"


@pytest.mark.order(2)
@pytest.mark.django_db
def test_locale_folders_exist():
    # Define the path to the locale directory
    locale_path = os.path.join(settings.BASE_DIR, 'locale')

    # Check if the locale directory exists
    assert os.path.isdir(locale_path), f"Locale directory does not exist at {locale_path}"

    # Define the expected language directories
    expected_languages = ['uz', 'ru', 'en']

    # Check if each expected language directory exists
    for lang in expected_languages:
        lang_path = os.path.join(locale_path, lang)
        assert os.path.isdir(lang_path), f"Language directory {lang} does not exist in {locale_path}"


@pytest.mark.order(3)
@pytest.mark.django_db
def test_modeltranslation_is_setup_correctly(user_factory):
    from modeltranslation.translator import translator

    assert translator.get_options_for_model(User) is not None

    instance = user_factory.create(first_name="Test")

    for lang_code, _ in settings.LANGUAGES:
        field_name = f'first_name_{lang_code}'
        assert hasattr(instance, field_name), f"{field_name} not found in {User.__name__}"

    instance.first_name_en = "English name"
    instance.first_name_uz = "O'zbekcha ism"
    instance.first_name_ru = "Русское имя"
    instance.save()

    instance.refresh_from_db()

    with translation.override('en'):
        assert instance.first_name == "English name"
    with translation.override('uz'):
        assert instance.first_name == "O'zbekcha ism"
    with translation.override('ru'):
        assert instance.first_name == "Русское имя"
