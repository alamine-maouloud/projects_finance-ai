package Vue;

import Modele.Session;
import Modele.Users.Client;

import javax.swing.*;
import javax.swing.plaf.basic.BasicScrollBarUI;
import java.awt.*;

public class Profil extends JFrame {

    private final Client client;

    public Profil(Client client) {
        this.client = client;

        setTitle("Profil - MEALAMHI");
        setDefaultCloseOperation(EXIT_ON_CLOSE);
        setSize(1200, 900);
        setLocationRelativeTo(null);

        JPanel contentPanel = new JPanel();
        contentPanel.setLayout(new BoxLayout(contentPanel, BoxLayout.Y_AXIS));
        contentPanel.setBackground(Color.WHITE);

        // ===== NAVIGATION =====
        JPanel navBar = new JPanel(new BorderLayout());
        navBar.setBackground(Color.WHITE);
        navBar.setBorder(BorderFactory.createEmptyBorder(10, 20, 10, 20));

        JLabel logo = new JLabel("MEALAMHI");
        logo.setFont(new Font("SansSerif", Font.BOLD, 22));
        navBar.add(logo, BorderLayout.WEST);

        JPanel navCenter = new JPanel(new FlowLayout(FlowLayout.CENTER, 20, 10));
        navCenter.setBackground(Color.WHITE);
        String[] centerLinks = { "\"Tropique\" - offres", "Nouveautés", "Printemps - ETE", "Rechercher un article" };
        for (String txt : centerLinks) {
            JLabel label = new JLabel(txt);
            label.setFont(new Font("SansSerif", Font.PLAIN, 14));
            navCenter.add(label);
        }
        navBar.add(navCenter, BorderLayout.CENTER);

        JPanel navRight = new JPanel(new FlowLayout(FlowLayout.RIGHT, 15, 10));
        navRight.setBackground(Color.WHITE);
        navRight.add(new JLabel("👤"));
        navRight.add(new JLabel("Panier"));
        navBar.add(navRight, BorderLayout.EAST);

        contentPanel.add(navBar);

        // ===== LIGNE CATEGORIES =====
        JPanel ligneMode = new JPanel(new FlowLayout(FlowLayout.CENTER, 30, 10));
        ligneMode.setBackground(Color.WHITE);
        ligneMode.setBorder(BorderFactory.createMatteBorder(1, 0, 1, 0, Color.BLACK));

        String[] categories = { "Chemise", "Pantalon", "Veste", "Pull", "Jupes", "Sweat", "Jean", "Manteau", "Doudoune" };
        for (String cat : categories) {
            JLabel label = new JLabel(cat);
            label.setFont(new Font("SansSerif", Font.PLAIN, 13));
            label.setForeground(Color.DARK_GRAY);
            ligneMode.add(label);
        }
        contentPanel.add(ligneMode);

        JLabel welcome = new JLabel("Bonjour " + client.getFirstName() + ",");
        welcome.setFont(new Font("SansSerif", Font.PLAIN, 20));
        welcome.setBorder(BorderFactory.createEmptyBorder(30, 50, 10, 0));
        contentPanel.add(welcome);

        JSeparator separator = new JSeparator();
        separator.setForeground(Color.LIGHT_GRAY);
        separator.setMaximumSize(new Dimension(Integer.MAX_VALUE, 1));
        contentPanel.add(separator);

        JPanel infoPanel = new JPanel();
        infoPanel.setLayout(new BoxLayout(infoPanel, BoxLayout.Y_AXIS));
        infoPanel.setBorder(BorderFactory.createEmptyBorder(30, 50, 30, 0));
        infoPanel.setBackground(Color.WHITE);

        JLabel titreInfos = new JLabel("Informations");
        titreInfos.setFont(new Font("SansSerif", Font.PLAIN, 16));
        infoPanel.add(titreInfos);
        infoPanel.add(Box.createVerticalStrut(10));

        infoPanel.add(new JLabel("Nom: " + client.getLastName()));
        infoPanel.add(new JLabel("Prénom: " + client.getFirstName()));
        infoPanel.add(new JLabel("Adresse: " + (client.getAdress() != null ? client.getAdress() : "[Non disponible]")));
        infoPanel.add(new JLabel("Email: " + client.getEmail()));
        infoPanel.add(new JLabel("Mot de passe: ********"));
        infoPanel.add(new JLabel("Téléphone: " + client.getPhone()));
        infoPanel.add(new JLabel("Type d'utilisateur: " + client.getTypeUser()));

        infoPanel.add(Box.createVerticalStrut(20));

        // ===== BOUTON "Modifier mes informations" =====
        JButton modifierBtn = new JButton("Modifier mes informations");
        modifierBtn.setAlignmentX(Component.LEFT_ALIGNMENT);
        modifierBtn.setBackground(Color.BLACK);
        modifierBtn.setForeground(Color.WHITE);
        modifierBtn.setFocusPainted(false);
        modifierBtn.setFont(new Font("SansSerif", Font.BOLD, 14));
        modifierBtn.setPreferredSize(new Dimension(200, 40));
        infoPanel.add(modifierBtn);

        infoPanel.add(Box.createVerticalStrut(15)); // espace entre les boutons

        // ===== BOUTON "Déconnexion" =====
        JButton deconnexionBtn = new JButton("Déconnexion");
        deconnexionBtn.setBackground(Color.BLACK);
        deconnexionBtn.setForeground(Color.WHITE);
        deconnexionBtn.setFocusPainted(false);
        deconnexionBtn.setFont(new Font("SansSerif", Font.BOLD, 14));
        deconnexionBtn.setPreferredSize(new Dimension(200, 40));
        deconnexionBtn.setAlignmentX(Component.LEFT_ALIGNMENT);
        infoPanel.add(deconnexionBtn);

        // Action bouton Déconnexion
        deconnexionBtn.addActionListener(e -> {
            Session.deconnexion();
            dispose();
            new Accueil(null);
        });

        infoPanel.add(Box.createVerticalStrut(10));

        // ===== LIEN "Retour à l'accueil" =====
        JLabel retourAccueilLabel = new JLabel("Retour à l'accueil");
        retourAccueilLabel.setFont(new Font("SansSerif", Font.PLAIN, 13));
        retourAccueilLabel.setForeground(Color.BLACK);
        retourAccueilLabel.setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));
        retourAccueilLabel.setAlignmentX(Component.LEFT_ALIGNMENT);
        retourAccueilLabel.setBorder(BorderFactory.createEmptyBorder(10, 0, 0, 0));

        retourAccueilLabel.addMouseListener(new java.awt.event.MouseAdapter() {
            @Override
            public void mouseClicked(java.awt.event.MouseEvent e) {
                dispose();
                new Accueil(null);
            }
        });

        infoPanel.add(retourAccueilLabel);

        contentPanel.add(infoPanel);

        // ===== FOOTER MULTI-COLONNES =====
        JPanel footerPanel = new JPanel(new GridLayout(1, 4, 40, 10));
        footerPanel.setBorder(BorderFactory.createEmptyBorder(40, 40, 40, 40));
        footerPanel.setBackground(Color.WHITE);

        footerPanel.add(createFooterColumn("Mentions légales et cookies", new String[]{
                "Mentions légales", "Conditions de vente", "Politique de confidentialité", "Conditions générales d'utilisation", "Accessibilité"
        }));

        footerPanel.add(createFooterColumn("FAQ", new String[]{
                "Compte", "Informations de livraison", "Commandes", "Paiements", "Retours & échanges"
        }));

        footerPanel.add(createFooterColumn("Entreprise", new String[]{
                "Nous contacter", "Carrière"
        }));

        footerPanel.add(createFooterColumn("Nous suivre", new String[]{
                "Instagram", "Tiktok", "X"
        }));

        contentPanel.add(new JSeparator());
        contentPanel.add(footerPanel);

        JLabel copyright = new JLabel("© 2025 Shopping Project - Tous droits réservés", SwingConstants.CENTER);
        copyright.setFont(new Font("SansSerif", Font.PLAIN, 12));
        copyright.setForeground(Color.GRAY);
        copyright.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10));
        contentPanel.add(copyright);

        // ===== SCROLLPANE avec Scrollbar stylé =====
        JScrollPane scrollPane = new JScrollPane(contentPanel);
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
                return createZeroButton();
            }

            @Override
            protected JButton createIncreaseButton(int orientation) {
                return createZeroButton();
            }

            private JButton createZeroButton() {
                JButton button = new JButton();
                button.setPreferredSize(new Dimension(0, 0));
                button.setOpaque(false);
                button.setContentAreaFilled(false);
                button.setBorderPainted(false);
                return button;
            }
        });

        setContentPane(scrollPane);
        setVisible(true);

        // Action bouton Modifier mes informations
        modifierBtn.addActionListener(e -> {
            new ModifierProfil(client);
        });
    }

    private JPanel createFooterColumn(String title, String[] items) {
        JPanel panel = new JPanel();
        panel.setLayout(new BoxLayout(panel, BoxLayout.Y_AXIS));
        panel.setBackground(Color.WHITE);

        JLabel header = new JLabel(title);
        header.setFont(new Font("SansSerif", Font.BOLD, 13));
        panel.add(header);
        for (String item : items) {
            JLabel link = new JLabel(item);
            link.setFont(new Font("SansSerif", Font.PLAIN, 13));
            panel.add(link);
        }
        return panel;
    }

    public static void main(String[] args) {
        Client testClient = new Client(1, "TestNom", "TestPrenom", "test@email.com", "1234", "6 rue Charcot", "0600000000", "client");
        SwingUtilities.invokeLater(() -> new Profil(testClient));
    }
}
