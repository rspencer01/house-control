from flask_sqlalchemy import SQLAlchemy
import time

db = SQLAlchemy()


class Light(db.Model):
    id = db.Column(db.String(80), primary_key=True)
    name = db.Column(db.String(120))

    def __repr__(self):
        return "<Light %r>" % self.name

    def latest_state(self):
        return self.lightstates[-1]

    def turn_on(self):
        self.lightstaterequests.append(
            LightStateRequest(time=int(time.time()), state=True, seen=False)
        )

    def turn_off(self):
        self.lightstaterequests.append(
            LightStateRequest(time=int(time.time()), state=False, seen=False)
        )


class LightState(db.Model):
    time = db.Column(db.Integer, primary_key=True)
    light_id = db.Column(db.String(80), db.ForeignKey("light.id"), primary_key=True)
    light = db.relationship(
        "Light", backref=db.backref("lightstates", lazy=True, order_by=time)
    )
    state = db.Column(db.Boolean)

    def __repr__(self):
        return "<LightState %r %r %r>" % (self.light_id, self.time, self.state)


class LightStateRequest(db.Model):
    time = db.Column(db.Integer, primary_key=True)
    light_id = db.Column(db.String(80), db.ForeignKey("light.id"), primary_key=True)
    light = db.relationship(
        "Light", backref=db.backref("lightstaterequests", lazy=True, order_by=time)
    )
    state = db.Column(db.Boolean)
    seen = db.Column(db.Boolean)

    def __repr__(self):
        return "<LightStateRequest %r %r %r %r>" % (
            self.light_id, self.time, self.state, self.seen
        )


class CustomMessage(db.Model):
    id = db.Column(db.Integer, unique=True, autoincrement=True, primary_key=True)
    time = db.Column(db.Integer)
    message = db.Column(db.String(80))
    seen = db.Column(db.Boolean)

    def __repr__(self):
        return "<CustomMessage %r %r %r %r>" % (
            self.id, self.time, self.message, self.seen
        )


class Schedule(db.Model):
    id = db.Column(db.Integer, unique=True, autoincrement=True, primary_key=True)
    name = db.Column(db.String(120))
    enabled = db.Column(db.Boolean)

    def __repr__(self):
        return "<Schedule %r %r %r>" % (self.id, self.name, self.enabled)


class ScheduleRule(db.Model):
    id = db.Column(db.Integer, unique=True, autoincrement=True, primary_key=True)
    light_id = db.Column(db.String(80), db.ForeignKey("light.id"))
    schedule_id = db.Column(db.Integer, db.ForeignKey("schedule.id"))
    schedule = db.relationship("Schedule", backref=db.backref("rules", lazy=True))
    # The time is stored in minutes past midnight
    time = db.Column(db.Integer)
    state = db.Column(db.Boolean)
    light = db.relationship("Light")
