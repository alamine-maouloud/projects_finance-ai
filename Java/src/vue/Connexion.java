package Vue;

import Controleur.Clientcontroleur;
import Modele.Session;
import Modele.Users.Client;
import Vue.Footer;

import javax.swing.*;
import javax.swing.plaf.basic.BasicScrollBarUI;
import java.awt.*;

public class Connexion extends JFrame {

    public Connexion() {
        setTitle("Connexion - MEALAMHI");
        setDefaultCloseOperation(EXIT_ON_CLOSE);
        setSize(1200, 900);
        setLocationRelativeTo(null);
        setBackground(Color.WHITE);

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
        String[] centerLinks = {
                "\"Tropique\" - offres", "Nouveautés", "Printemps - ETE", "Rechercher un article"
        };
        for (String txt : centerLinks) {
            navCenter.add(createNavLabel(txt));
        }
        navBar.add(navCenter, BorderLayout.CENTER);

        JPanel navRight = new JPanel(new FlowLayout(FlowLayout.RIGHT, 15, 10));
        navRight.setBackground(Color.WHITE);

        JLabel profilIcon = createNavLabel("\uD83D\uDC64");
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

        // ===== FORMULAIRE DE CONNEXION =====
        JPanel centerWrapper = new JPanel(new GridBagLayout());
        centerWrapper.setBackground(Color.WHITE);

        JPanel formCard = new JPanel(new GridBagLayout());
        formCard.setBackground(new Color(247, 247, 247));
        formCard.setBorder(BorderFactory.createCompoundBorder(
                BorderFactory.createLineBorder(Color.LIGHT_GRAY, 1, true),
                BorderFactory.createEmptyBorder(30, 30, 30, 30)
        ));
        formCard.setMaximumSize(new Dimension(450, 450));
        formCard.setAlignmentX(Component.CENTER_ALIGNMENT);

        GridBagConstraints gbc = new GridBagConstraints();
        gbc.fill = GridBagConstraints.HORIZONTAL;
        gbc.insets = new Insets(10, 10, 10, 10);
        gbc.gridx = 0;
        gbc.gridy = 0;

        JLabel emailLabel = new JLabel("E-mail *");
        emailLabel.setFont(new Font("SansSerif", Font.PLAIN, 14));
        formCard.add(emailLabel, gbc);

        gbc.gridy++;
        JTextField emailField = new JTextField();
        emailField.setPreferredSize(new Dimension(300, 40));
        formCard.add(emailField, gbc);

        gbc.gridy++;
        JLabel passLabel = new JLabel("Mot de passe *");
        passLabel.setFont(new Font("SansSerif", Font.PLAIN, 14));
        formCard.add(passLabel, gbc);

        gbc.gridy++;
        JPasswordField passwordField = new JPasswordField();
        passwordField.setPreferredSize(new Dimension(300, 40));
        formCard.add(passwordField, gbc);

        gbc.gridy++;
        JButton loginButton = new JButton("Connexion");
        loginButton.setBackground(Color.BLACK);
        loginButton.setForeground(Color.WHITE);
        loginButton.setFocusPainted(false);
        loginButton.setFont(new Font("SansSerif", Font.BOLD, 16));
        loginButton.setPreferredSize(new Dimension(200, 45));
        loginButton.setAlignmentX(Component.CENTER_ALIGNMENT);
        formCard.add(loginButton, gbc);

        loginButton.addActionListener(e -> {
            String email = emailField.getText().trim();
            String password = new String(passwordField.getPassword());

            if (email.isEmpty() || password.isEmpty()) {
                JOptionPane.showMessageDialog(this, "Veuillez remplir tous les champs.", "Erreur", JOptionPane.ERROR_MESSAGE);
                return;
            }

            boolean connexionOK = Clientcontroleur.verifierConnexion(email, password);

            if (connexionOK) {
                Client utilisateur = Clientcontroleur.getClientParEmail(email);
                if (utilisateur != null) {
                    Session.setClient(utilisateur);
                    this.dispose();
                    SwingUtilities.invokeLater(() -> new Accueil(utilisateur));
                } else {
                    JOptionPane.showMessageDialog(this, "Erreur interne lors de la récupération du client.", "Erreur", JOptionPane.ERROR_MESSAGE);
                }
            } else {
                JOptionPane.showMessageDialog(this, "Identifiants incorrects.", "Erreur", JOptionPane.ERROR_MESSAGE);
            }
        });

        JPanel contentWrapper = new JPanel();
        contentWrapper.setLayout(new BoxLayout(contentWrapper, BoxLayout.Y_AXIS));
        contentWrapper.setBackground(Color.WHITE);
        contentWrapper.add(formCard);

        // ===== Liens sous le formulaire =====
        JLabel registerLabel = new JLabel("Pas encore client ? Inscription");
        registerLabel.setFont(new Font("SansSerif", Font.PLAIN, 13));
        registerLabel.setForeground(Color.BLACK);
        registerLabel.setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));
        registerLabel.setAlignmentX(Component.CENTER_ALIGNMENT);
        registerLabel.setBorder(BorderFactory.createEmptyBorder(20, 0, 0, 0));

        JLabel retourAccueilLabel = new JLabel("Retour à l'accueil");
        retourAccueilLabel.setFont(new Font("SansSerif", Font.PLAIN, 13));
        retourAccueilLabel.setForeground(Color.BLACK);
        retourAccueilLabel.setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));
        retourAccueilLabel.setAlignmentX(Component.CENTER_ALIGNMENT);
        retourAccueilLabel.setBorder(BorderFactory.createEmptyBorder(10, 0, 20, 0));

        retourAccueilLabel.addMouseListener(new java.awt.event.MouseAdapter() {
            @Override
            public void mouseClicked(java.awt.event.MouseEvent evt) {
                dispose();
                SwingUtilities.invokeLater(() -> new Accueil(null));
            }
        });

        contentWrapper.add(registerLabel);
        contentWrapper.add(retourAccueilLabel);

        centerWrapper.add(contentWrapper);
        centerWrapper.setBorder(BorderFactory.createEmptyBorder(100, 0, 100, 0));

        mainPanel.add(centerWrapper);

        // ===== FOOTER =====
        mainPanel.add(new Footer());

        // ===== SCROLL GLOBAL =====
        JScrollPane bigScroll = new JScrollPane(mainPanel);
        bigScroll.setVerticalScrollBarPolicy(JScrollPane.VERTICAL_SCROLLBAR_ALWAYS);
        bigScroll.getVerticalScrollBar().setUnitIncrement(20);

        bigScroll.getVerticalScrollBar().setUI(new BasicScrollBarUI() {
            @Override
            protected void configureScrollBarColors() {
                this.thumbColor = new Color(160, 160, 160);
                this.trackColor = new Color(245, 245, 245);
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

        setContentPane(bigScroll);
        setVisible(true);
    }

    private JLabel createNavLabel(String text) {
        JLabel label = new JLabel(text);
        label.setFont(new Font("SansSerif", Font.PLAIN, 14));
        label.setForeground(Color.BLACK);
        return label;
    }

    public static void main(String[] args) {
        SwingUtilities.invokeLater(Connexion::new);
    }
}
