from house_server import db

class Light(db.Model):
  id = db.Column(db.String(80), primary_key=True)
  name = db.Column(db.String(120)) 

  def __repr__(self):
    return "<Light %r>" % self.name

