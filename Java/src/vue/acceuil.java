package Vue;

import Modele.Session;
import Modele.Users.Client;

import javax.swing.*;
import javax.swing.plaf.basic.BasicScrollBarUI;
import java.awt.*;

public class Accueil extends JFrame {

    private final Client client;

    public Accueil(Client client) {
        this.client = client;
        Session.setClient(client);

        setTitle("Jacquemus - Nouveautés");
        setDefaultCloseOperation(EXIT_ON_CLOSE);
        setSize(1200, 900);
        setLocationRelativeTo(null);

        JPanel mainPanel = new JPanel();
        mainPanel.setLayout(new BoxLayout(mainPanel, BoxLayout.Y_AXIS));
        mainPanel.setBackground(Color.WHITE);

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
            navCenter.add(createNavLabel(txt));
        }
        navBar.add(navCenter, BorderLayout.CENTER);

        JPanel navRight = new JPanel(new FlowLayout(FlowLayout.RIGHT, 15, 10));
        navRight.setBackground(Color.WHITE);

        JLabel profilIcon = createNavLabel("👤");
        profilIcon.setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));
        profilIcon.addMouseListener(new java.awt.event.MouseAdapter() {
            @Override
            public void mouseClicked(java.awt.event.MouseEvent evt) {
                dispose();
                if (Session.estConnecte()) {
                    new Profil(Session.getClient());
                } else {
                    new Connexion();
                }
            }
        });

        navRight.add(profilIcon);
        navRight.add(createNavLabel("Panier"));
        navBar.add(navRight, BorderLayout.EAST);

        mainPanel.add(navBar);

        // ===== CATEGORIES =====
        JPanel ligneMode = new JPanel(new FlowLayout(FlowLayout.CENTER, 30, 10));
        ligneMode.setBackground(Color.WHITE);
        ligneMode.setBorder(BorderFactory.createMatteBorder(1, 0, 1, 0, Color.BLACK));

        String[] categories = { "Chemise", "Pantalon", "Veste", "Pull", "Jupes", "Sweat", "Jean", "Manteau", "Doudoune" };
        for (String cat : categories) {
            JLabel label = new JLabel(cat);
            label.setFont(new Font("SansSerif", Font.PLAIN, 13));
            label.setForeground(Color.DARK_GRAY);
            label.setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));

            label.addMouseListener(new java.awt.event.MouseAdapter() {
                @Override
                public void mouseClicked(java.awt.event.MouseEvent e) {
                    dispose(); // ferme Accueil

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
                        default:
                            // aucune action
                            break;
                    }
                }
            });

            ligneMode.add(label);
        }

        mainPanel.add(ligneMode);

        // ===== IMAGES =====
        JPanel galerie = new JPanel(new GridLayout(3, 3, 20, 20));
        galerie.setBackground(Color.WHITE);
        galerie.setBorder(BorderFactory.createEmptyBorder(30, 40, 30, 40));

        String[] images = {
                "look1.png", "look2.png", "look3.png",
                "look4.png", "look5.png", "look6.png",
                "look7.png", "look8.png", "look9.png"
        };

        for (String img : images) {
            try {
                ImageIcon icon = new ImageIcon("images/" + img);
                Image scaled = icon.getImage().getScaledInstance(250, 350, Image.SCALE_SMOOTH);
                JLabel imgLabel = new JLabel(new ImageIcon(scaled));
                imgLabel.setHorizontalAlignment(SwingConstants.CENTER);
                galerie.add(imgLabel);
            } catch (Exception e) {
                galerie.add(new JLabel("Image non trouvée"));
            }
        }

        JScrollPane scrollPane = new JScrollPane(galerie);
        scrollPane.setPreferredSize(new Dimension(1200, 720));
        scrollPane.getVerticalScrollBar().setUnitIncrement(20);
        scrollPane.setBorder(null);
        scrollPane.getViewport().setBackground(Color.WHITE);

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

        mainPanel.add(scrollPane);

        // ===== FOOTER =====
        mainPanel.add(new Footer());

        setContentPane(mainPanel);
        setVisible(true);
    }

    private JLabel createNavLabel(String text) {
        JLabel label = new JLabel(text);
        label.setFont(new Font("SansSerif", Font.PLAIN, 14));
        label.setForeground(Color.BLACK);
        return label;
    }

    public static void main(String[] args) {
        SwingUtilities.invokeLater(() -> new Accueil(null));
    }
}

