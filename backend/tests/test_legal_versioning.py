
from app.integrations.legal_versioning import LegalVersioning

def test_snapshot():

    versioning = LegalVersioning()

    result = versioning.create_snapshot("CRP")

    assert result["snapshot_created"]
