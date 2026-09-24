package Vue;

import javax.swing.*;
import javax.swing.plaf.basic.BasicScrollBarUI;
import java.awt.*;
import Modele.Panier;
import Modele.PanierItem;
import Modele.Session;

public class PageChemise extends JFrame {

    public PageChemise() {
        setTitle("Chemises - Boutique");
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
                if (Session.estConnecte()) {
                    new Profil(Session.getClient()); // Ouvre Profil si connecté
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

        // ===== BARRE CATEGORIES CLIQUABLES =====
        JPanel ligneMode = new JPanel(new FlowLayout(FlowLayout.CENTER, 30, 10));
        ligneMode.setBackground(Color.WHITE);
        ligneMode.setBorder(BorderFactory.createMatteBorder(1, 0, 1, 0, Color.BLACK));

        String[] categories = { "Chemise", "Pantalon", "Veste", "Pull", "Jupes", "Sweat", "Jean", "Manteau", "Doudoune" };
        for (final String cat : categories) {  // Rendre la variable `cat` finale ici
            JLabel label = new JLabel(cat);
            label.setFont(new Font("SansSerif", Font.PLAIN, 13));
            label.setForeground(Color.DARK_GRAY);
            label.setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));
            label.addMouseListener(new java.awt.event.MouseAdapter() {
                @Override
                public void mouseClicked(java.awt.event.MouseEvent e) {
                    dispose();
                    switch (cat.toLowerCase()) {
                        case "chemise":
                            SwingUtilities.invokeLater(PageChemise::new);
                            break;
                        case "pantalon":
                            SwingUtilities.invokeLater(PagePantalon::new);
                            break;
                        case "veste":
                            SwingUtilities.invokeLater(PageVeste::new);
                            break;
                        case "pull":
                            SwingUtilities.invokeLater(PagePull::new);
                            break;
                        case "jupes":
                            SwingUtilities.invokeLater(PageJupe::new);
                            break;
                        case "sweat":
                            SwingUtilities.invokeLater(PageSweat::new);
                            break;
                        case "jean":
                            SwingUtilities.invokeLater(PageJean::new);
                            break;
                        case "manteau":
                            SwingUtilities.invokeLater(PageManteau::new);
                            break;
                        case "doudoune":
                            SwingUtilities.invokeLater(PageDoudoune::new);
                            break;
                    }
                }
            });
            ligneMode.add(label);
        }

        headerPanel.add(ligneMode);
        globalPanel.add(headerPanel, BorderLayout.NORTH);

        // ===== CONTENU DES CHEMISES =====
        JPanel containerPanel = new JPanel();
        containerPanel.setLayout(new BoxLayout(containerPanel, BoxLayout.Y_AXIS));
        containerPanel.setBackground(Color.WHITE);
        containerPanel.setBorder(BorderFactory.createEmptyBorder(20, 40, 20, 40));

        // Exemple de 3 articles dans le panier
        String[] images = { "chemise1.png", "chemise2.png", "chemise3.png" };  // Remplacer avec le chemin des images
        String[] descriptions = { "Chemise Croco Cuir", "Chemise Pasadena", "Chemise de Costume" };
        String[] tailles = { "Taille 44", "Taille 42", "Taille 40" };
        String[] prix = { "1990 €", "650 €", "590 €" };
        int[] quantities = { 1, 2, 1 };

        for (int i = 0; i < images.length; i++) {
            final String descriptionProduit = descriptions[i];  // rendre les variables finales
            final String prixProduit = prix[i];
            final int quantityProduit = quantities[i];
            final String tailleProduit = tailles[i];

            JPanel rowPanel = new JPanel(new FlowLayout(FlowLayout.LEFT, 30, 20));
            rowPanel.setBackground(Color.WHITE);

            // Photo du produit
            JLabel imgLabel = new JLabel(new ImageIcon(new ImageIcon(images[i]).getImage().getScaledInstance(150, 150, Image.SCALE_SMOOTH)));
            rowPanel.add(imgLabel);

            // Détails du produit (quantité, description, prix, taille)
            JPanel detailsPanel = new JPanel();
            detailsPanel.setLayout(new BoxLayout(detailsPanel, BoxLayout.Y_AXIS));
            detailsPanel.setBackground(Color.WHITE);
            detailsPanel.setBorder(BorderFactory.createEmptyBorder(0, 20, 0, 0));

            JLabel descriptionLabel = new JLabel(descriptionProduit);
            descriptionLabel.setFont(new Font("SansSerif", Font.PLAIN, 16));
            detailsPanel.add(descriptionLabel);

            JLabel prixLabel = new JLabel(prixProduit);
            prixLabel.setFont(new Font("SansSerif", Font.BOLD, 14));
            detailsPanel.add(prixLabel);

            // Choix de la taille avec JComboBox personnalisé
            String[] taillesDisponibles = { "XS", "S", "M", "L", "XL" };
            JComboBox<String> tailleComboBox = new JComboBox<>(taillesDisponibles);
            tailleComboBox.setSelectedItem(tailleProduit);
            tailleComboBox.setFont(new Font("SansSerif", Font.PLAIN, 14));
            tailleComboBox.setBackground(new Color(245, 245, 245)); // Fond doux
            tailleComboBox.setForeground(Color.BLACK);
            tailleComboBox.setBorder(BorderFactory.createLineBorder(Color.LIGHT_GRAY, 1));
            tailleComboBox.addActionListener(e -> {
                tailleComboBox.setBackground(new Color(230, 230, 230)); // changement de fond au clic
            });
            detailsPanel.add(new JLabel("Taille"));
            detailsPanel.add(tailleComboBox);

            // Quantité avec JSpinner personnalisé
            SpinnerNumberModel model = new SpinnerNumberModel(quantityProduit, 1, 10, 1);
            JSpinner quantitySpinner = new JSpinner(model);
            quantitySpinner.setFont(new Font("SansSerif", Font.PLAIN, 14));
            JComponent editor = quantitySpinner.getEditor();
            JTextField textField = ((JSpinner.DefaultEditor) editor).getTextField();
            textField.setHorizontalAlignment(JTextField.CENTER);
            textField.setBackground(new Color(245, 245, 245)); // Arrière-plan doux
            detailsPanel.add(new JLabel("Quantité"));
            detailsPanel.add(quantitySpinner);

            rowPanel.add(detailsPanel);

            // Ajouter au panier
            JButton ajouterBtn = new JButton("Ajouter au panier");
            ajouterBtn.setBackground(Color.BLACK);
            ajouterBtn.setForeground(Color.WHITE);
            ajouterBtn.setFocusPainted(false);
            ajouterBtn.setFont(new Font("SansSerif", Font.BOLD, 14));
            ajouterBtn.setBorder(BorderFactory.createEmptyBorder(10, 20, 10, 20));

            // Action pour ajouter au panier
            ajouterBtn.addActionListener(e -> {
                // Récupérer la quantité et la taille sélectionnée
                int quantite = (int) quantitySpinner.getValue();
                String tailleSelectionnee = (String) tailleComboBox.getSelectedItem();

                // Créer un nouvel item panier
                PanierItem item = new PanierItem(descriptionProduit, Double.parseDouble(prixProduit.replace(" €", "")), quantite, tailleSelectionnee);

                // Ajouter cet item au panier
                Panier.ajouterAuPanier(item);

                // Afficher un message pour confirmer
                JOptionPane.showMessageDialog(this, "Produit ajouté au panier !");
            });

            rowPanel.add(ajouterBtn);

            containerPanel.add(rowPanel);
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
        SwingUtilities.invokeLater(PageChemise::new);
    }
}
