
class RGPDManager:

    def anonymize_retention(self, process_id):

        return {
            "process_id": process_id,
            "retention_policy_applied": True
        }

    def right_to_access(self, citizen_id):

        return {
            "citizen_id": citizen_id,
            "access_granted": True
        }
