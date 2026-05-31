
class LegalVersioning:

    def create_snapshot(self, diploma):

        return {
            "snapshot_created": True,
            "diploma": diploma
        }

    def compare_versions(self, old, new):

        return {
            "changes_detected": []
        }
