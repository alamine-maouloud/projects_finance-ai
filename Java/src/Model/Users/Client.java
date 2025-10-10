package Modele.Users;

public class Client {

    private int idUsers;
    private String lastName;
    private String firstName;
    private String email;
    private String passWord;
    private String adress;
    private String phone;
    private String typeUser;

    // === Constructeur complet ===
    public Client(int idUsers, String lastName, String firstName, String email, String passWord, String adress, String phone, String typeUser) {
        this.idUsers = idUsers;
        this.lastName = lastName;
        this.firstName = firstName;
        this.email = email;
        this.passWord = passWord;
        this.adress = adress;
        this.phone = phone;
        this.typeUser = typeUser;
    }

    // === Getters ===
    public int getIdUsers() {
        return idUsers;
    }

    public String getLastName() {
        return lastName;
    }

    public String getFirstName() {
        return firstName;
    }

    public String getEmail() {
        return email;
    }

    public String getPassWord() {
        return passWord;
    }

    public String getAdress() {
        return adress;
    }

    public String getPhone() {
        return phone;
    }

    public String getTypeUser() {
        return typeUser;
    }

    // === Setters (optionnels) ===
    public void setIdUsers(int idUsers) {
        this.idUsers = idUsers;
    }

    public void setLastName(String lastName) {
        this.lastName = lastName;
    }

    public void setFirstName(String firstName) {
        this.firstName = firstName;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public void setPassWord(String passWord) {
        this.passWord = passWord;
    }

    public void setAdress(String adress) {
        this.adress = adress;
    }

    public void setPhone(String phone) {
        this.phone = phone;
    }

    public void setTypeUser(String typeUser) {
        this.typeUser = typeUser;
    }

    @Override
    public String toString() {
        return lastName + " " + firstName + " (" + email + ")";
    }
}
