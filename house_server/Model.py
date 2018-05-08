from house_server import db


class Light(db.Model):
    id = db.Column(db.String(80), primary_key=True)
    name = db.Column(db.String(120))

    def __repr__(self):
        return "<Light %r>" % self.name


class LightState(db.Model):
    time = db.Column(db.Integer, primary_key=True)
    light_id = db.Column(db.String(80), db.ForeignKey("light.id"), primary_key=True)
    light = db.relationship("Light", backref=db.backref("lightstates", lazy=True))
    state = db.Column(db.Boolean)

    def __repr__(self):
        return "<LightState %r %r %r>" % (self.light_id, self.time, self.state)