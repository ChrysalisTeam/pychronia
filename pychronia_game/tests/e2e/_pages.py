# -*- coding: utf-8 -*-

ERROR_PAGE_MARKERS = ("Traceback (most recent call last)", "Exception Value", "Exception Type")


def login_as_player(page, base_url, game_id, username, password):
    page.goto("%s/%s/guest/login/" % (base_url, game_id))
    page.fill("#id_secret_username", username)
    page.fill("#id_secret_password", password)
    page.click("#login")
    page.wait_for_url("%s/%s/%s/*" % (base_url, game_id, username))


def login_as_superuser(page, base_url, username, password, next_path="/administration/"):
    page.goto("%s/admin/login/?next=%s" % (base_url, next_path))
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click('input[type="submit"]')


def goto_as(page, base_url, game_id, username, path=""):
    """Navigates to a game page as the given effective username.
    For a Django superuser session, this transparently impersonates that username
    (the game's AuthenticationMiddleware honors the URL username as the
    impersonation target when the real session is a superuser one)."""
    url = "%s/%s/%s/%s" % (base_url, game_id, username, path.lstrip("/"))
    return page.goto(url)


def set_impersonation_writability(page, base_url, game_id, writable):
    url = "%s/%s/anyuser/profile/" % (base_url, game_id)
    page.context.request.post(url, form={"_set_impersonation_writability_": "true" if writable else "false"})


def logout(page, base_url, game_id):
    page.goto("%s/%s/anyuser/logout/" % (base_url, game_id))


def assert_page_ok(page, response=None, expected_status=200):
    if response is not None:
        assert response.status == expected_status, (response.url, response.status)
    content = page.content()
    for marker in ERROR_PAGE_MARKERS:
        assert marker not in content, (page.url, marker)
