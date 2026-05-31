
class AuditEngine:

    def validate(self, result):

        issues = []

        if "factos" not in result:
            issues.append("Factos em falta")

        return {
            "valid": len(issues) == 0,
            "issues": issues
        }
