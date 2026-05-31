
from app.security.rbac import RBACManager, Role

def test_admin_permissions():

    manager = RBACManager()

    assert manager.has_permission(
        Role.ADMIN,
        "anything"
    )
