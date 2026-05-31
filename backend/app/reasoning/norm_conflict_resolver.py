
class NormConflictResolver:

    def resolve(
        self,
        norma_a,
        norma_b
    ):

        return {
            "conflict_detected": True,
            "hierarchy_applied": True,
            "prevalent_norm": norma_a
        }
