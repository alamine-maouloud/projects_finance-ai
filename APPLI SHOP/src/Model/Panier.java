package Modele;

import java.util.ArrayList;

public class Panier {

    // Liste des articles du panier
    private static ArrayList<PanierItem> items = new ArrayList<>();

    // Méthode pour ajouter un produit au panier
    public static void ajouterAuPanier(PanierItem item) {
        items.add(item);
    }

    // Méthode pour obtenir tous les articles du panier
    public static ArrayList<PanierItem> getArticles() {
        return items;
    }

    // Méthode pour calculer le total
    public static double calculerTotal() {
        double total = 0;
        for (PanierItem item : items) {
            total += item.getPrix() * item.getQuantite();
        }
        return total;
    }
}
