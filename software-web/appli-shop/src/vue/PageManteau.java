package Vue;

import javax.swing.*;
import java.awt.*;

public class PageManteau extends JFrame {

    public PageManteau() {
        setTitle("Manteaux - Boutique");
        setDefaultCloseOperation(DISPOSE_ON_CLOSE);
        setSize(1200, 900);
        setLocationRelativeTo(null);

        JPanel mainPanel = new JPanel();
        mainPanel.setLayout(new BoxLayout(mainPanel, BoxLayout.Y_AXIS));
        mainPanel.setBackground(Color.WHITE);

        // ===== NAVIGATION PRINCIPALE =====
        JPanel navBar = new JPanel(new BorderLayout());
        navBar.setBackground(Color.WHITE);
        navBar.setBorder(BorderFactory.createEmptyBorder(10, 20, 10, 20));

        JLabel logo = new JLabel("MEALAMHI");
        logo.setFont(new Font("SansSerif", Font.BOLD, 22));
        navBar.add(logo, BorderLayout.WEST);

        JPanel navCenter = new JPanel(new FlowLayout(FlowLayout.CENTER, 20, 10));
        navCenter.setBackground(Color.WHITE);
        String[] centerLinks = {
                "Tropique - offres", "Nouveautés", "Printemps - ETE", "Rechercher un article"
        };
        for (String txt : centerLinks) {
            navCenter.add(new JLabel(txt));
        }
        navBar.add(navCenter, BorderLayout.CENTER);

        JPanel navRight = new JPanel(new FlowLayout(FlowLayout.RIGHT, 15, 10));
        navRight.setBackground(Color.WHITE);
        navRight.add(new JLabel("👤"));
        navRight.add(new JLabel("Panier"));
        navBar.add(navRight, BorderLayout.EAST);

        mainPanel.add(navBar);

        // ===== BARRE ENCADRÉE AVEC CATEGORIES =====
        JPanel ligneMode = new JPanel(new FlowLayout(FlowLayout.CENTER, 30, 10));
        ligneMode.setBackground(Color.WHITE);
        ligneMode.setBorder(BorderFactory.createMatteBorder(1, 0, 1, 0, Color.BLACK));

        String[] categories = {
                "Chemise", "Pantalon", "Veste", "Pull", "Jupes", "Sweat", "Jean", "Manteau", "Doudoune"
        };
        for (String cat : categories) {
            JLabel label = new JLabel(cat);
            label.setFont(new Font("SansSerif", Font.PLAIN, 13));
            label.setForeground(Color.DARK_GRAY);
            ligneMode.add(label);
        }

        mainPanel.add(ligneMode);

        // ===== CONTENU DES MANTEAUX =====
        JPanel containerPanel = new JPanel();
        containerPanel.setLayout(new BoxLayout(containerPanel, BoxLayout.Y_AXIS));
        containerPanel.setBackground(Color.WHITE);
        containerPanel.setBorder(BorderFactory.createEmptyBorder(20, 40, 20, 40));

        String[] images = {
                "manteau1.png", "manteau2.png", "manteau3.png",
                "manteau4.png", "manteau5.png", "manteau6.png",
                "manteau7.png", "manteau8.png", "manteau9.png"
        };

        String[] noms = {
                "Trench Caruso", "Manteau Télo", "Manteau Bari",
                "Manteau Caruso", "Manteau Télo", "Manteau Ovalo",
                "Marina", "Manteau Norma", "Blouson Bari"
        };

        String[] prix = {
                "1490 €", "2990 €", "1590 €",
                "1790 €", "4490 €", "1690 €",
                "2790 €", "2390 €", "1290 €"
        };

        for (int i = 0; i < images.length; i += 3) {
            JPanel rowPanel = new JPanel(new FlowLayout(FlowLayout.CENTER, 30, 20));
            rowPanel.setBackground(Color.WHITE);

            for (int j = i; j < i + 3 && j < images.length; j++) {
                JPanel itemPanel = new JPanel();
                itemPanel.setLayout(new BoxLayout(itemPanel, BoxLayout.Y_AXIS));
                itemPanel.setBackground(Color.WHITE);
                itemPanel.setBorder(BorderFactory.createLineBorder(Color.LIGHT_GRAY));

                try {
                    ImageIcon icon = new ImageIcon(images[j]);
                    Image scaled = icon.getImage().getScaledInstance(250, 350, Image.SCALE_SMOOTH);
                    JLabel imgLabel = new JLabel(new ImageIcon(scaled));
                    imgLabel.setAlignmentX(Component.CENTER_ALIGNMENT);
                    itemPanel.add(imgLabel);
                } catch (Exception e) {
                    itemPanel.add(new JLabel("Image non trouvée"));
                }

                JLabel nomLabel = new JLabel(noms[j], SwingConstants.CENTER);
                nomLabel.setFont(new Font("SansSerif", Font.PLAIN, 14));
                nomLabel.setAlignmentX(Component.CENTER_ALIGNMENT);
                itemPanel.add(Box.createVerticalStrut(10));
                itemPanel.add(nomLabel);

                JLabel prixLabel = new JLabel(prix[j], SwingConstants.CENTER);
                prixLabel.setFont(new Font("SansSerif", Font.BOLD, 14));
                prixLabel.setAlignmentX(Component.CENTER_ALIGNMENT);
                itemPanel.add(prixLabel);

                JButton ajouterBtn = new JButton("Ajouter au panier");
                ajouterBtn.setAlignmentX(Component.CENTER_ALIGNMENT);
                itemPanel.add(Box.createVerticalStrut(10));
                itemPanel.add(ajouterBtn);

                rowPanel.add(itemPanel);
            }

            containerPanel.add(rowPanel);
        }

        JScrollPane scrollPane = new JScrollPane(containerPanel);
        scrollPane.getVerticalScrollBar().setUnitIncrement(20);
        scrollPane.setPreferredSize(new Dimension(1200, 700));
        mainPanel.add(scrollPane);

        setContentPane(mainPanel);
        setVisible(true);
    }

    public static void main(String[] args) {
        SwingUtilities.invokeLater(PageManteau::new);
    }
}
