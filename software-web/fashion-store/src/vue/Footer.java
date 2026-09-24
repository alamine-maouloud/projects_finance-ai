package Vue;

import javax.swing.*;
import java.awt.*;

public class Footer extends JPanel {

    public Footer() {
        setLayout(new BoxLayout(this, BoxLayout.Y_AXIS));
        setBackground(Color.WHITE);

        // Ligne séparatrice
        JSeparator separator = new JSeparator();
        separator.setForeground(Color.LIGHT_GRAY);
        separator.setMaximumSize(new Dimension(Integer.MAX_VALUE, 1));
        add(separator);

        // Liens
        JPanel linksPanel = new JPanel(new GridLayout(1, 4, 40, 10));
        linksPanel.setBorder(BorderFactory.createEmptyBorder(40, 40, 20, 40));
        linksPanel.setBackground(Color.WHITE);

        linksPanel.add(createColumn("Mentions légales et cookies", new String[]{
                "Mentions légales", "Conditions de vente", "Politique de confidentialité", "Conditions générales d'utilisation", "Accessibilité"
        }));

        linksPanel.add(createColumn("FAQ", new String[]{
                "Compte", "Informations de livraison", "Commandes", "Paiements", "Retours & échanges", "Guide des tailles", "Carte Cadeau"
        }));

        linksPanel.add(createColumn("Entreprise", new String[]{
                "Nous contacter", "Nos boutiques", "Prendre un rendez-vous en boutique", "Carrière"
        }));

        linksPanel.add(createColumn("Nous suivre", new String[]{
                "Instagram", "Facebook", "Tiktok", "X", "Pinterest"
        }));

        add(linksPanel);

        // Copyright
        JLabel copyright = new JLabel("\u00a9 MEALAMHI 2025", SwingConstants.LEFT);
        copyright.setFont(new Font("SansSerif", Font.PLAIN, 12));
        copyright.setForeground(Color.GRAY);
        copyright.setBorder(BorderFactory.createEmptyBorder(10, 40, 10, 0));
        copyright.setAlignmentX(Component.LEFT_ALIGNMENT);
        add(copyright);
    }

    private JPanel createColumn(String title, String[] items) {
        JPanel column = new JPanel();
        column.setLayout(new BoxLayout(column, BoxLayout.Y_AXIS));
        column.setBackground(Color.WHITE);

        JLabel header = new JLabel(title);
        header.setFont(new Font("SansSerif", Font.BOLD, 13));
        header.setBorder(BorderFactory.createEmptyBorder(0, 0, 10, 0));
        column.add(header);

        for (String item : items) {
            JLabel link = new JLabel(item);
            link.setFont(new Font("SansSerif", Font.PLAIN, 13));
            column.add(link);
        }
        return column;
    }
}
