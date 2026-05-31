
class ErrorTracker:

    def capture(self, error):

        return {
            "error": str(error),
            "captured": True
        }
