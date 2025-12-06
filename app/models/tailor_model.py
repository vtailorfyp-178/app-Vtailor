class Tailor:
    def __init__(self, tailor_id, name, specialty, experience, contact_info):
        self.tailor_id = tailor_id
        self.name = name
        self.specialty = specialty
        self.experience = experience
        self.contact_info = contact_info

    def __repr__(self):
        return f"<Tailor {self.name}, Specialty: {self.specialty}, Experience: {self.experience} years>"

    def to_dict(self):
        return {
            "tailor_id": self.tailor_id,
            "name": self.name,
            "specialty": self.specialty,
            "experience": self.experience,
            "contact_info": self.contact_info,
        }