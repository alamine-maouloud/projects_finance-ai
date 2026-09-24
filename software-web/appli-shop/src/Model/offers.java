package Modele;

public class offers {
    private int id;
    private String description;
    private String offerType;
    private double value;
    private Integer quantityCondition;
    private java.time.LocalDateTime startDate;
    private java.time.LocalDateTime endDate;

    public offers() {}

    public int getId() { return id; }
    public void setId(int id) { this.id = id; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public String getOfferType() { return offerType; }
    public void setOfferType(String offerType) { this.offerType = offerType; }
    public double getValue() { return value; }
    public void setValue(double value) { this.value = value; }
    public Integer getQuantityCondition() { return quantityCondition; }
    public void setQuantityCondition(Integer quantityCondition) { this.quantityCondition = quantityCondition; }
    public java.time.LocalDateTime getStartDate() { return startDate; }
    public void setStartDate(java.time.LocalDateTime startDate) { this.startDate = startDate; }
    public java.time.LocalDateTime getEndDate() { return endDate; }
    public void setEndDate(java.time.LocalDateTime endDate) { this.endDate = endDate; }
}
