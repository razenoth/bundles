from app import db

class Estimate(db.Model):
    __tablename__ = 'estimate'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, nullable=False)
    customer_name = db.Column(db.String(128), nullable=False)
    customer_address = db.Column(db.String(256))
    status = db.Column(db.String(32), nullable=False, default='draft')

    items = db.relationship(
        'EstimateItem',
        back_populates='estimate',
        cascade='all, delete-orphan'
    )

class EstimateItem(db.Model):
    __tablename__ = 'estimate_item'
    id = db.Column(db.Integer, primary_key=True)
    estimate_id = db.Column(
        db.Integer,
        db.ForeignKey('estimate.id', ondelete='CASCADE'),
        nullable=False
    )
    # 'product' or 'bundle'
    type = db.Column(db.String(32), nullable=False)
    # points at either a product or bundle id
    object_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    qty = db.Column(db.Integer, nullable=False, default=1)
    cost = db.Column(db.Numeric(10, 2), nullable=False)
    retail = db.Column(db.Numeric(10, 2), nullable=False)

    estimate = db.relationship('Estimate', back_populates='items')
