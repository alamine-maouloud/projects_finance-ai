package Modele;

public class payment {
    private int id;
    private int orderId;
    private double amountPaid;
    private java.time.LocalDate paymentDate;
    private String methodPayment;
    private String paymentStatus;

    public payment() {}

    public int getId() { return id; }
    public void setId(int id) { this.id = id; }
    public int getOrderId() { return orderId; }
    public void setOrderId(int orderId) { this.orderId = orderId; }
    public double getAmountPaid() { return amountPaid; }
    public void setAmountPaid(double amountPaid) { this.amountPaid = amountPaid; }
    public java.time.LocalDate getPaymentDate() { return paymentDate; }
    public void setPaymentDate(java.time.LocalDate paymentDate) { this.paymentDate = paymentDate; }
    public String getMethodPayment() { return methodPayment; }
    public void setMethodPayment(String methodPayment) { this.methodPayment = methodPayment; }
    public String getPaymentStatus() { return paymentStatus; }
    public void setPaymentStatus(String paymentStatus) { this.paymentStatus = paymentStatus; }
}