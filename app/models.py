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
        """Total cost of visible line items only.

        When a bundle is added to an estimate we store a parent line for the
        bundle itself and child lines for each product in that bundle.  The
        child lines allow per‑estimate price customisation but should not be
        counted again when calculating estimate totals.  Therefore only
        top‑level items (those without a parent) contribute to the summary
        figures.
        """
        return sum(
            i.quantity * i.unit_price for i in self.items if i.parent_id is None
        )

    @property
    def total_retail(self):
        return sum(
            i.quantity * i.retail for i in self.items if i.parent_id is None
        )

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
    parent_id    = db.Column(db.Integer, db.ForeignKey('estimate_item.id'))

    children = db.relationship(
        'EstimateItem',
        backref=db.backref('parent', remote_side=[id]),
        lazy=True
    )

    @property
    def line_total(self):
        return self.quantity * self.unit_price

class RSProduct(db.Model):
    __tablename__ = 'rs_product'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    description = db.Column(db.Text)
    long_description = db.Column(db.Text)
    price_cost = db.Column(db.Float)
    price_retail = db.Column(db.Float)
    price_wholesale = db.Column(db.Float)
    quantity = db.Column(db.Float)
    desired_stock_level = db.Column(db.Float)
    reorder_at = db.Column(db.Float)
    maintain_stock = db.Column(db.Boolean)
    taxable = db.Column(db.Boolean)
    serialized = db.Column(db.Boolean)
    upc_code = db.Column(db.String)
    category_path = db.Column(db.String)
    product_category = db.Column(db.String)
    vendor_ids = db.Column(db.JSON)
    photos = db.Column(db.JSON)
    location_quantities = db.Column(db.JSON)
    sku = db.Column(db.String, nullable=True)


class RSCustomer(db.Model):
    __tablename__ = 'rs_customer'
    id = db.Column(db.Integer, primary_key=True)
    firstname = db.Column(db.String)
    lastname = db.Column(db.String)
    fullname = db.Column(db.String)
    business_name = db.Column(db.String)
    email = db.Column(db.String)
    phone = db.Column(db.String)
    mobile = db.Column(db.String)
    address = db.Column(db.String)
    address2 = db.Column(db.String)
    city = db.Column(db.String)
    state = db.Column(db.String)
    zip = db.Column(db.String)
    created_at = db.Column(db.String)
    updated_at = db.Column(db.String)
    disabled = db.Column(db.Boolean)
    properties = db.Column(db.JSON)
    tax_rate_id = db.Column(db.Integer)


class RSVendor(db.Model):
    __tablename__ = 'rs_vendor'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    email = db.Column(db.String)


class RSInvoice(db.Model):
    __tablename__ = 'rs_invoice'
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String)
    status = db.Column(db.String)
    date = db.Column(db.String)
    due_date = db.Column(db.String)
    subtotal = db.Column(db.Float)
    total = db.Column(db.Float)
    tax = db.Column(db.Float)
    customer_id = db.Column(db.Integer)
    ticket_id = db.Column(db.Integer)
    pdf_url = db.Column(db.String)
    location_id = db.Column(db.Integer)
    created_at = db.Column(db.String)
    updated_at = db.Column(db.String)


class RSEstimate(db.Model):
    __tablename__ = 'rs_estimate'
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String)
    status = db.Column(db.String)
    date = db.Column(db.String)
    subtotal = db.Column(db.Float)
    total = db.Column(db.Float)
    tax = db.Column(db.Float)
    customer_id = db.Column(db.Integer)
    ticket_id = db.Column(db.Integer)
    pdf_url = db.Column(db.String)
    location_id = db.Column(db.Integer)
    created_at = db.Column(db.String)
    updated_at = db.Column(db.String)


class RSLineItem(db.Model):
    __tablename__ = 'rs_line_item'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, nullable=True)
    estimate_id = db.Column(db.Integer, nullable=True)
    item = db.Column(db.String)
    name = db.Column(db.String)
    cost = db.Column(db.Float)
    price = db.Column(db.Float)
    quantity = db.Column(db.Float)
    product_id = db.Column(db.Integer)
    taxable = db.Column(db.Boolean)
    discount_percent = db.Column(db.Float)
    discount_dollars = db.Column(db.Float)
    position = db.Column(db.Integer)


class RSPurchaseOrder(db.Model):
    __tablename__ = 'rs_purchase_order'
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer)
    number = db.Column(db.String)
    status = db.Column(db.String)
    expected_date = db.Column(db.String)
    total = db.Column(db.Float)
    shipping = db.Column(db.Float)
    other = db.Column(db.Float)
    line_items = db.Column(db.JSON)
