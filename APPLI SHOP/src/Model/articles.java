package Modele;

public class articles {
    private int id;
    private String name;
    private String description;
    private String brand;
    private double unitPrice;
    private Double bulkPrice;
    private int stock;

    public articles() {}

    public int getId() { return id; }
    public void setId(int id) { this.id = id; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public String getBrand() { return brand; }
    public void setBrand(String brand) { this.brand = brand; }
    public double getUnitPrice() { return unitPrice; }
    public void setUnitPrice(double unitPrice) { this.unitPrice = unitPrice; }
    public Double getBulkPrice() { return bulkPrice; }
    public void setBulkPrice(Double bulkPrice) { this.bulkPrice = bulkPrice; }
    public int getStock() { return stock; }
    public void setStock(int stock) { this.stock = stock; }
}