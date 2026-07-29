import pytest
from core.models import FlakinessScore, Project, TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def project_with_score(db):
    project = Project.objects.create(name="Demo", slug="demo")
    case = TestCase.objects.create(project=project, test_id="t::x")
    FlakinessScore.objects.create(case=case, probability=0.5, impact=1.0)
    return project, case


def test_index_requires_login(client):
    response = client.get(reverse("index"))
    assert response.status_code == 302
    assert reverse("login") in response.url


def test_index_hides_projects_user_is_not_a_member_of(client, project_with_score):
    user = User.objects.create_user(username="outsider", password="pw")
    client.force_login(user)

    response = client.get(reverse("index"))
    assert response.status_code == 200
    assert b"t::x" not in response.content


def test_index_shows_projects_user_is_a_member_of(client, project_with_score):
    project, _ = project_with_score
    user = User.objects.create_user(username="member", password="pw")
    project.members.add(user)
    client.force_login(user)

    response = client.get(reverse("index"))
    assert response.status_code == 200
    assert b"t::x" in response.content


def test_superuser_sees_all_projects(client, project_with_score):
    admin = User.objects.create_superuser(username="root", password="pw", email="root@example.com")
    client.force_login(admin)

    response = client.get(reverse("index"))
    assert response.status_code == 200
    assert b"t::x" in response.content


def test_test_detail_404s_for_non_member(client, project_with_score):
    _, case = project_with_score
    user = User.objects.create_user(username="outsider", password="pw")
    client.force_login(user)

    response = client.get(reverse("test_detail", args=[case.id]))
    assert response.status_code == 404


def test_test_detail_ok_for_member(client, project_with_score):
    project, case = project_with_score
    user = User.objects.create_user(username="member", password="pw")
    project.members.add(user)
    client.force_login(user)

    response = client.get(reverse("test_detail", args=[case.id]))
    assert response.status_code == 200
