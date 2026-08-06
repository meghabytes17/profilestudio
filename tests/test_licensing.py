"""License lookup/adoption logic. No Tk — the screen itself is not unit-tested."""
import sys

import pytest

from incoming_profile_utility import licensing


class FakeLicense:
    def __init__(self, holder="Acme Fab GmbH", days_remaining=42, linked_to_pc=True):
        self.holder = holder
        self.days_remaining = days_remaining
        self.linked_to_pc = linked_to_pc


class FakeLicenseError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class FakeUsher:
    """Stand-in for the vendor extension: any file whose text is 'good' verifies."""
    LicenseError = FakeLicenseError

    @staticmethod
    def check_license(path):
        try:
            text = open(path).read().strip()
        except OSError:
            raise FakeLicenseError("not_found", f"cannot open {path}")
        if text != "good":
            raise FakeLicenseError("bad_format", "bad magic")
        return FakeLicense()

    @staticmethod
    def machine_id_hash_hex():
        return "a" * 64


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Licensing pointed at a throwaway app folder with the fake extension loaded."""
    monkeypatch.setattr(licensing, "usher", lambda: FakeUsher)
    monkeypatch.setattr(licensing, "app_dir", lambda: tmp_path)
    monkeypatch.setattr(licensing, "_pointer_file", lambda: tmp_path / "pointer.txt")
    return tmp_path


def test_default_license_is_next_to_the_executable(app):
    assert licensing.default_license_path() == app / "license.lic"


def test_finds_and_reports_a_valid_default_license(app):
    (app / "license.lic").write_text("good")
    status = licensing.find_license()
    assert status.ok and status.holder == "Acme Fab GmbH"
    assert status.path == app / "license.lic"
    assert status.expiry_text == "Expires in 42 days."


def test_missing_license_reports_not_found(app):
    status = licensing.find_license()
    assert not status.ok
    assert status.code == "not_found"
    assert status.reason == "No license file was found."


def test_invalid_license_keeps_the_vendor_code_and_message(app):
    (app / "license.lic").write_text("junk")
    status = licensing.find_license()
    assert not status.ok
    assert status.code == "bad_format"
    assert status.detail == "bad magic"


def test_a_real_reason_beats_not_found_from_another_candidate(app, tmp_path):
    """Default file exists but is broken, remembered file is gone: show the broken one."""
    (app / "license.lic").write_text("junk")
    licensing.remember_path(tmp_path / "gone.lic")
    assert licensing.find_license().code == "bad_format"


def test_remembered_path_is_used_when_there_is_no_default(app, tmp_path):
    elsewhere = tmp_path / "share" / "site.lic"
    elsewhere.parent.mkdir()
    elsewhere.write_text("good")
    licensing.remember_path(elsewhere)
    status = licensing.find_license()
    assert status.ok and status.path == elsewhere


def test_install_copies_the_file_next_to_the_app(app, tmp_path):
    picked = tmp_path / "downloads" / "from_vendor.lic"
    picked.parent.mkdir()
    picked.write_text("good")
    path, copied = licensing.install(picked)
    assert copied and path == app / "license.lic"
    assert (app / "license.lic").read_text() == "good"
    assert licensing.remembered_path() is None          # default location wins
    assert licensing.find_license().ok


@pytest.mark.skipif(sys.platform.startswith("win"), reason="chmod does not deny writes here")
def test_install_remembers_the_path_when_the_app_folder_is_read_only(app, tmp_path, monkeypatch):
    picked = tmp_path / "from_vendor.lic"
    picked.write_text("good")
    monkeypatch.setattr(licensing, "app_dir", lambda: tmp_path / "nonexistent")
    path, copied = licensing.install(picked)
    assert not copied and path == picked.resolve()
    assert licensing.remembered_path() == picked.resolve()


def test_perpetual_license_says_no_expiry(app):
    status = licensing.LicenseStatus(ok=True, holder="X", days_remaining=None)
    assert status.expiry_text == "No expiry date — perpetual license."
    assert not status.expires_soon


def test_license_expiring_within_a_month_is_flagged():
    assert licensing.LicenseStatus(ok=True, days_remaining=30).expires_soon
    assert not licensing.LicenseStatus(ok=True, days_remaining=31).expires_soon


def test_missing_extension_fails_closed_in_a_frozen_build(monkeypatch):
    monkeypatch.setattr(licensing, "usher", lambda: None)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    try:
        status = licensing.check("anything.lic")
    finally:
        monkeypatch.delattr(sys, "frozen", raising=False)
    assert not status.ok and status.code == "component_missing"
    assert status.reason == "The license component is missing from this installation."


def test_missing_extension_allows_running_from_source(monkeypatch):
    monkeypatch.setattr(licensing, "usher", lambda: None)
    assert not getattr(sys, "frozen", False)
    status = licensing.check("anything.lic")
    assert status.ok and status.dev_mode


def test_machine_signature_comes_from_the_extension(app):
    assert licensing.machine_signature() == "a" * 64


def test_machine_signature_is_empty_without_the_extension(monkeypatch):
    monkeypatch.setattr(licensing, "usher", lambda: None)
    assert licensing.machine_signature() == ""
