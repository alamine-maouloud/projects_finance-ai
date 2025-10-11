package Modele;

public class PanierItem {

    private String nom;
    private double prix;
    private int quantite;
    private String taille;

    // Constructeur
    public PanierItem(String nom, double prix, int quantite, String taille) {
        this.nom = nom;
        this.prix = prix;
        this.quantite = quantite;
        this.taille = taille;
    }

    // Getters
    public String getNom() {
        return nom;
    }

    public double getPrix() {
        return prix;
    }

    public int getQuantite() {
        return quantite;
    }

    public String getTaille() {
        return taille;
    }
}
