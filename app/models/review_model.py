class Review:
    def __init__(self, reviewer_id, tailor_id, rating, comment):
        self.reviewer_id = reviewer_id  # ID of the user who wrote the review
        self.tailor_id = tailor_id        # ID of the tailor being reviewed
        self.rating = rating              # Rating given by the reviewer (e.g., 1 to 5)
        self.comment = comment            # Review comment text

    def to_dict(self):
        """Convert the Review object to a dictionary for easy serialization."""
        return {
            "reviewer_id": self.reviewer_id,
            "tailor_id": self.tailor_id,
            "rating": self.rating,
            "comment": self.comment
        }