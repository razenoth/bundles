from app import db

class Bundle(db.Model):
    __tablename__ = 'bundle'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    items       = db.relationship('BundleItem', backref='bundle', lazy=True)

class BundleItem(db.Model):
    __tablename__ = 'bundle_item'
    id                = db.Column(db.Integer, primary_key=True)
    bundle_id         = db.Column(db.Integer, db.ForeignKey('bundle.id'), nullable=False)

    # New field for product name
    product_name      = db.Column(db.String(200), nullable=False)

    # Existing description now holds the product description
    description       = db.Column(db.Text, nullable=True)

    quantity          = db.Column(db.Integer, default=1)
    cost              = db.Column(db.Float,   default=0.0)
    retail            = db.Column(db.Float,   default=0.0)

class Estimate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(200))
    customer_address = db.Column(db.String(200))
    items = db.relationship('EstimateItem', backref='estimate', lazy=True)

    @property
    def total(self):
        return sum(i.quantity * i.unit_price for i in self.items)

class EstimateItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    estimate_id = db.Column(db.Integer, db.ForeignKey('estimate.id'), nullable=False)
    description = db.Column(db.String(200))
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, default=0.0)
    notes = db.Column(db.String(200), default='')
