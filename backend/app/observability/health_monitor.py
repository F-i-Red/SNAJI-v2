
class HealthMonitor:

    def check_database(self):

        return {
            "database": "healthy"
        }

    def check_rag(self):

        return {
            "rag": "healthy"
        }

    def check_agents(self):

        return {
            "agents": "healthy"
        }

    def global_health(self):

        return {
            "database": self.check_database(),
            "rag": self.check_rag(),
            "agents": self.check_agents()
        }
