class Error(Exception):
    pass


class SupplierSKUNotFound(Error):
    def __init__(self, sku):
        self.sku = sku

    def msg(self):
        return f"Supplier SKU not found for product {self.sku}"
