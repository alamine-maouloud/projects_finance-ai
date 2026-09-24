package Vue;

import javax.swing.*;
import javax.swing.plaf.basic.BasicScrollBarUI;
import java.awt.*;
import Modele.Panier;
import Modele.PanierItem;

public class PagePanier extends JFrame {

    public PagePanier() {
        setTitle("Panier - Boutique");
        setDefaultCloseOperation(DISPOSE_ON_CLOSE);
        setSize(1200, 900);
        setLocationRelativeTo(null);

        // ===== Structure principale en BorderLayout =====
        JPanel globalPanel = new JPanel(new BorderLayout());
        globalPanel.setBackground(Color.WHITE);

        // ===== HEADER =====
        JPanel headerPanel = new JPanel();
        headerPanel.setLayout(new BoxLayout(headerPanel, BoxLayout.Y_AXIS));
        headerPanel.setBackground(Color.WHITE);

        // ===== NAVIGATION PRINCIPALE =====
        JPanel navBar = new JPanel(new BorderLayout());
        navBar.setBackground(Color.WHITE);
        navBar.setBorder(BorderFactory.createEmptyBorder(10, 20, 10, 20));

        JLabel logo = new JLabel("MEALAMHI");
        logo.setFont(new Font("SansSerif", Font.BOLD, 22));
        navBar.add(logo, BorderLayout.WEST);

        JPanel navCenter = new JPanel(new FlowLayout(FlowLayout.CENTER, 20, 10));
        navCenter.setBackground(Color.WHITE);
        String[] centerLinks = { "Tropique - offres", "Nouveautés", "Printemps - ETE", "Rechercher un article" };
        for (String txt : centerLinks) {
            navCenter.add(new JLabel(txt));
        }
        navBar.add(navCenter, BorderLayout.CENTER);

        JPanel navRight = new JPanel(new FlowLayout(FlowLayout.RIGHT, 15, 10));
        navRight.setBackground(Color.WHITE);

        // ===== ICONE DU PROFIL (cliquable) =====
        JLabel profilIcon = new JLabel("👤");
        profilIcon.setFont(new Font("SansSerif", Font.PLAIN, 22));
        profilIcon.setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));
        profilIcon.addMouseListener(new java.awt.event.MouseAdapter() {
            @Override
            public void mouseClicked(java.awt.event.MouseEvent evt) {
                dispose(); // Ferme la page actuelle
                if (Modele.Session.estConnecte()) {
                    new Profil(Modele.Session.getClient()); // Ouvre Profil si connecté
                } else {
                    new Connexion(); // Ouvre Connexion si non connecté
                }
            }
        });
        navRight.add(profilIcon);

        // ===== ICONE DU PANIER (cliquable) =====
        JLabel panierIcon = new JLabel("🛒");
        panierIcon.setFont(new Font("SansSerif", Font.PLAIN, 22));
        panierIcon.setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));
        panierIcon.addMouseListener(new java.awt.event.MouseAdapter() {
            @Override
            public void mouseClicked(java.awt.event.MouseEvent evt) {
                dispose(); // Ferme la page actuelle
                SwingUtilities.invokeLater(PagePanier::new); // Ouvre la page Panier
            }
        });
        navRight.add(panierIcon);

        navBar.add(navRight, BorderLayout.EAST);

        headerPanel.add(navBar);

        // ===== CONTENU DU PANIER =====
        JPanel containerPanel = new JPanel();
        containerPanel.setLayout(new BoxLayout(containerPanel, BoxLayout.Y_AXIS));
        containerPanel.setBackground(Color.WHITE);
        containerPanel.setBorder(BorderFactory.createEmptyBorder(20, 40, 20, 40));

        // Vérifie si le panier est vide
        if (Panier.getArticles().isEmpty()) {
            JLabel emptyMessage = new JLabel("Votre panier est vide");
            emptyMessage.setFont(new Font("SansSerif", Font.BOLD, 16));
            emptyMessage.setForeground(Color.RED);
            containerPanel.add(emptyMessage);
        } else {
            // Si le panier n'est pas vide, affiche les articles ajoutés
            for (PanierItem item : Panier.getArticles()) {
                JPanel rowPanel = new JPanel(new FlowLayout(FlowLayout.LEFT, 30, 20));
                rowPanel.setBackground(Color.WHITE);

                // Photo du produit
                JLabel imgLabel = new JLabel(new ImageIcon(new ImageIcon("path_to_image.jpg").getImage().getScaledInstance(150, 150, Image.SCALE_SMOOTH))); // Remplacer par un chemin valide
                rowPanel.add(imgLabel);

                // Détails du produit (quantité, description, prix, taille)
                JPanel detailsPanel = new JPanel();
                detailsPanel.setLayout(new BoxLayout(detailsPanel, BoxLayout.Y_AXIS));
                detailsPanel.setBackground(Color.WHITE);
                detailsPanel.setBorder(BorderFactory.createEmptyBorder(0, 20, 0, 0));

                JLabel descriptionLabel = new JLabel(item.getNom());
                descriptionLabel.setFont(new Font("SansSerif", Font.PLAIN, 16));
                detailsPanel.add(descriptionLabel);

                JLabel prixLabel = new JLabel(item.getPrix() + " €");
                prixLabel.setFont(new Font("SansSerif", Font.BOLD, 14));
                detailsPanel.add(prixLabel);

                JLabel tailleLabel = new JLabel("Taille : " + item.getTaille());
                tailleLabel.setFont(new Font("SansSerif", Font.PLAIN, 14));
                detailsPanel.add(tailleLabel);

                JLabel quantityLabel = new JLabel("Quantité : " + item.getQuantite());
                quantityLabel.setFont(new Font("SansSerif", Font.PLAIN, 14));
                detailsPanel.add(quantityLabel);

                rowPanel.add(detailsPanel);

                containerPanel.add(rowPanel);
            }
        }

        // ===== FINALISER LA COMMANDE =====
        JPanel finalPanel = new JPanel(new FlowLayout(FlowLayout.CENTER, 30, 20));
        finalPanel.setBackground(Color.WHITE);

        JButton finalizeButton = new JButton("Finaliser la commande");
        finalizeButton.setBackground(Color.BLACK);
        finalizeButton.setForeground(Color.WHITE);
        finalizeButton.setFocusPainted(false);
        finalizeButton.setFont(new Font("SansSerif", Font.BOLD, 14));
        finalizeButton.setBorder(BorderFactory.createEmptyBorder(10, 20, 10, 20));
        finalPanel.add(finalizeButton);

        containerPanel.add(finalPanel);

        // ===== VIDER LE PANIER =====
        JPanel viderPanierPanel = new JPanel(new FlowLayout(FlowLayout.CENTER, 30, 20));
        viderPanierPanel.setBackground(Color.WHITE);

        JButton viderButton = new JButton("Vider le panier");
        viderButton.setBackground(Color.RED);
        viderButton.setForeground(Color.WHITE);
        viderButton.setFocusPainted(false);
        viderButton.setFont(new Font("SansSerif", Font.BOLD, 14));
        viderButton.setBorder(BorderFactory.createEmptyBorder(10, 20, 10, 20));
        viderPanierPanel.add(viderButton);

        // Action pour vider le panier
        viderButton.addActionListener(e -> {
            Panier.getArticles().clear(); // Vide la liste d'articles
            JOptionPane.showMessageDialog(this, "Le panier a été vidé.");
            dispose(); // Redirige vers une nouvelle page avec panier vide
            SwingUtilities.invokeLater(PagePanier::new); // Recharge la page panier
        });

        containerPanel.add(viderPanierPanel);

        // ===== SCROLLPANE pour tout scroller si besoin =====
        JScrollPane scrollPane = new JScrollPane(containerPanel);
        scrollPane.setVerticalScrollBarPolicy(JScrollPane.VERTICAL_SCROLLBAR_ALWAYS);
        scrollPane.getVerticalScrollBar().setUnitIncrement(20);
        scrollPane.getVerticalScrollBar().setUI(new BasicScrollBarUI() {
            @Override
            protected void configureScrollBarColors() {
                this.thumbColor = new Color(180, 180, 180);
                this.trackColor = Color.WHITE;
            }

            @Override
            protected JButton createDecreaseButton(int orientation) {
                return new JButton();
            }

            @Override
            protected JButton createIncreaseButton(int orientation) {
                return new JButton();
            }
        });

        globalPanel.add(scrollPane, BorderLayout.CENTER);

        // ===== FOOTER EN BAS FIXE =====
        globalPanel.add(new Footer(), BorderLayout.SOUTH);

        setContentPane(globalPanel);
        setVisible(true);
    }

    public static void main(String[] args) {
        SwingUtilities.invokeLater(PagePanier::new);
    }
}
