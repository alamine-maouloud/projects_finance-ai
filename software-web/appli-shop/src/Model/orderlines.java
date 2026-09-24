package Modele;

public class orderlines {
    private int id;
    private int orderId;
    private int articleId;
    private int quantity;
    private double totalPrice;

    public orderlines() {}

    public int getId() { return id; }
    public void setId(int id) { this.id = id; }
    public int getOrderId() { return orderId; }
    public void setOrderId(int orderId) { this.orderId = orderId; }
    public int getArticleId() { return articleId; }
    public void setArticleId(int articleId) { this.articleId = articleId; }
    public int getQuantity() { return quantity; }
    public void setQuantity(int quantity) { this.quantity = quantity; }
    public double getTotalPrice() { return totalPrice; }
    public void setTotalPrice(double totalPrice) { this.totalPrice = totalPrice; }
}