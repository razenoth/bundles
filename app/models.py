from app import db

class Bundle(db.Model):
    __tablename__ = 'bundle'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    items       = db.relationship(
                    'BundleItem',
                    backref='bundle',
                    lazy=True,
                    cascade='all, delete-orphan'
                  )

class BundleItem(db.Model):
    __tablename__ = 'bundle_item'
    id           = db.Column(db.Integer, primary_key=True)
    bundle_id    = db.Column(db.Integer, db.ForeignKey('bundle.id'), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    description  = db.Column(db.Text, nullable=True, default='')    # ← NEW
    quantity     = db.Column(db.Integer, default=1)
    unit_price   = db.Column(db.Float, default=0.0)
    retail       = db.Column(db.Float, default=0.0)

class Estimate(db.Model):
    __tablename__ = 'estimate'
    id                = db.Column(db.Integer, primary_key=True)
    customer_id       = db.Column(db.Integer, nullable=True)
    customer_name     = db.Column(db.String(200), nullable=False)
    customer_address  = db.Column(db.String(200))
    status            = db.Column(db.String(32), nullable=False, default='draft')

    items = db.relationship(
        'EstimateItem',
        backref='estimate',
        lazy=True,
        cascade='all, delete-orphan'
    )

    @property
    def total_cost(self):
        return sum(i.quantity * i.unit_price for i in self.items)

    @property
    def total_retail(self):
        return sum(i.quantity * i.retail for i in self.items)

    @property
    def profit(self):
        return self.total_retail - self.total_cost

class EstimateItem(db.Model):
    __tablename__ = 'estimate_item'
    id           = db.Column(db.Integer, primary_key=True)
    estimate_id  = db.Column(db.Integer, db.ForeignKey('estimate.id'), nullable=False)
    type         = db.Column(db.String(32), nullable=False)  # 'product' or 'bundle'
    object_id    = db.Column(db.Integer, nullable=False)     # product.id or bundle.id
    name         = db.Column(db.String(200), nullable=False)
    description  = db.Column(db.Text)
    quantity     = db.Column(db.Integer, default=1)
    unit_price   = db.Column(db.Float, default=0.0)
    retail       = db.Column(db.Float, default=0.0)
    notes        = db.Column(db.String(200), default='')

    @property
    def line_total(self):
        return self.quantity * self.unit_price
