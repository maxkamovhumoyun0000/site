from pathlib import Path


PAGE = Path(__file__).resolve().parents[1] / "app" / "page.tsx"


def detail_modal_source() -> str:
    source = PAGE.read_text(encoding="utf-8")
    start = source.index("{/* ── User Detail Modal ── */}")
    end = source.index("{/* ── Placement preparation modal ── */}", start)
    return source[start:end]


def test_user_detail_edits_inline_and_keeps_placement_in_its_own_modal():
    detail = detail_modal_source()

    # The detail popup owns its editing and per-group pricing UI; it must not
    # send the admin to a second edit popup.
    assert "<AdminUserEditPanel" in detail
    assert "setAdminUserEditTarget(selectedDetailUserRow)" not in detail

    # Placement subject/required settings are deliberately isolated behind
    # the preparation action, rather than always occupying the detail popup.
    assert "setPlacementPrepTarget" in detail
    assert "Placement Subject" not in detail
    assert "Placement Required" not in detail


def test_inline_user_editor_uses_one_full_name_field():
    source = PAGE.read_text(encoding="utf-8")
    start = source.index("function AdminUserEditPanel(")
    end = source.index("function AdminGroupCreatePanel(", start)
    editor = source[start:end]

    assert "const [fullName, setFullName]" in editor
    assert "F.I.SH" in editor
    assert "setFirstName(" not in editor
    assert "setLastName(" not in editor


def test_student_detail_has_synchronized_family_group_management():
    detail = detail_modal_source()

    assert "Oila guruhi" in detail
    assert "familyDetailCandidates" in detail
    assert "familyDetailCandidateQuery" in detail
    assert "linkFamilyCandidate" in detail
    assert "unlinkFamilyCandidate" in detail
    assert "Tavsiya" in detail


def test_family_linking_uses_existing_shared_family_group_api():
    source = PAGE.read_text(encoding="utf-8")

    assert '"/admin/family-groups"' in source
    assert "/members" in source
    assert "loadFamilyGroups(true)" in source


def test_family_groups_page_recommends_same_surname_students():
    source = PAGE.read_text(encoding="utf-8")
    family_page = source[source.index('if (section === "family-groups")'):]

    assert "pickerFamilyLastNames" in family_page
    assert "suggestedLastName" in source
    assert "Tavsiya" in family_page


def test_user_block_and_delete_require_confirmation():
    source = PAGE.read_text(encoding="utf-8")
    start = source.index("async function toggleUserBlocked")
    end = source.index("async function approvePublicRegistration", start)
    controls = source[start:end]

    assert "window.confirm" in controls
    assert "deleteManagedUser" in controls


def test_all_roles_use_the_student_profile_layout():
    source = PAGE.read_text(encoding="utf-8")
    start = source.index("let content: React.ReactNode = null;")
    end = source.index("return (", start)
    router = source[start:end]

    assert router.count("<StudentProfile") >= 5
    assert "<RoleProfilePanel" not in router


def test_navigation_icons_are_uppercase_letters():
    sidebar = (PAGE.parent / "ui" / "dashboard-sidebar.tsx").read_text(encoding="utf-8")
    start = sidebar.index("export function sectionIconGlyph")
    end = sidebar.index("function SidebarDiamondWordmark", start)
    glyphs = sidebar[start:end]

    assert "toUpperCase()" in glyphs
    assert 'home: "⌂"' not in glyphs


def test_teacher_editor_does_not_show_parent_phone_field():
    source = PAGE.read_text(encoding="utf-8")
    start = source.index("function AdminUserEditPanel(")
    end = source.index("function AdminGroupCreatePanel(", start)
    editor = source[start:end]

    assert "!isTeacherLike" in editor
