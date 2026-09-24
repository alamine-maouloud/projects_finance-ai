package Vue;

import Controleur.Clientcontroleur;
import Modele.Users.Client;
import Modele.Session;
import javax.swing.*;
import javax.swing.plaf.basic.BasicScrollBarUI;
import java.awt.*;

public class Inscription extends JFrame {

    public Inscription() {
        setTitle("Inscription - MEALAMHI");
        setDefaultCloseOperation(EXIT_ON_CLOSE);
        setSize(1200, 900);
        setLocationRelativeTo(null);
        setBackground(Color.WHITE);

        JPanel mainPanel = new JPanel();
        mainPanel.setLayout(new BoxLayout(mainPanel, BoxLayout.Y_AXIS));
        mainPanel.setBackground(Color.WHITE);

        // ===== NAVIGATION =====
        JPanel navBar = createNavBar();
        mainPanel.add(navBar);

        // ===== CATEGORIES =====
        JPanel ligneMode = createCategories();
        mainPanel.add(ligneMode);

        // ===== FORMULAIRE INSCRIPTION =====
        JPanel centerWrapper = new JPanel(new GridBagLayout());
        centerWrapper.setBackground(Color.WHITE);

        JPanel formCard = new JPanel(new GridBagLayout());
        formCard.setBackground(new Color(247, 247, 247));
        formCard.setBorder(BorderFactory.createCompoundBorder(
                BorderFactory.createLineBorder(Color.LIGHT_GRAY, 1, true),
                BorderFactory.createEmptyBorder(30, 30, 30, 30)
        ));
        formCard.setMaximumSize(new Dimension(450, 600));

        GridBagConstraints gbc = new GridBagConstraints();
        gbc.fill = GridBagConstraints.HORIZONTAL;
        gbc.insets = new Insets(10, 10, 10, 10);
        gbc.gridx = 0;
        gbc.gridy = 0;

        JTextField nomField = new JTextField();
        JTextField prenomField = new JTextField();
        JTextField adresseField = new JTextField();
        JTextField telField = new JTextField();
        JTextField emailField = new JTextField();
        JPasswordField passwordField = new JPasswordField();

        formCard.add(createInputField("Nom *", nomField), gbc);
        gbc.gridy++;
        formCard.add(createInputField("Prénom *", prenomField), gbc);
        gbc.gridy++;
        formCard.add(createInputField("Adresse *", adresseField), gbc);
        gbc.gridy++;
        formCard.add(createInputField("Téléphone *", telField), gbc);
        gbc.gridy++;
        formCard.add(createInputField("E-mail *", emailField), gbc);
        gbc.gridy++;
        formCard.add(createInputField("Mot de passe *", passwordField), gbc);
        gbc.gridy++;

        JButton inscriptionButton = new JButton("Inscription");
        inscriptionButton.setBackground(Color.BLACK);
        inscriptionButton.setForeground(Color.WHITE);
        inscriptionButton.setFocusPainted(false);
        inscriptionButton.setFont(new Font("SansSerif", Font.BOLD, 16));
        inscriptionButton.setPreferredSize(new Dimension(200, 45));
        inscriptionButton.setAlignmentX(Component.CENTER_ALIGNMENT);
        formCard.add(inscriptionButton, gbc);

        JPanel contentWrapper = new JPanel();
        contentWrapper.setLayout(new BoxLayout(contentWrapper, BoxLayout.Y_AXIS));
        contentWrapper.setBackground(Color.WHITE);
        contentWrapper.add(formCard);

        // ===== Liens sous formulaire =====
        JLabel dejaClientLabel = createLinkLabel("Déjà client ? Connexion", () -> {
            dispose();
            new Connexion();
        });

        JLabel retourAccueilLabel = createLinkLabel("Retour à l'accueil", () -> {
            dispose();
            new Accueil(null);
        });

        contentWrapper.add(dejaClientLabel);
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
                this.thumbColor = new Color(180, 180, 180);
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

        // ===== Action du bouton Inscription =====
        inscriptionButton.addActionListener(e -> {
            String nom = nomField.getText().trim();
            String prenom = prenomField.getText().trim();
            String adresse = adresseField.getText().trim();
            String tel = telField.getText().trim();
            String email = emailField.getText().trim();
            String pass = new String(passwordField.getPassword()).trim();

            if (nom.isEmpty() || prenom.isEmpty() || adresse.isEmpty() || tel.isEmpty() || email.isEmpty() || pass.isEmpty()) {
                JOptionPane.showMessageDialog(this, "Veuillez remplir tous les champs.", "Erreur", JOptionPane.ERROR_MESSAGE);
                return;
            }

            if (!tel.matches("\\d+")) {
                JOptionPane.showMessageDialog(this, "Le téléphone doit contenir uniquement des chiffres.", "Erreur", JOptionPane.ERROR_MESSAGE);
                return;
            }

            // ===== Vérification Email Existant =====
            if (Clientcontroleur.emailExiste(email)) {
                JOptionPane.showMessageDialog(this, "Email déja existant, connectez-vous !", "Email déjà utilisé", JOptionPane.ERROR_MESSAGE);
            } else {
                Client nouveauClient = new Client(
                        0,
                        nom,
                        prenom,
                        email,
                        pass,
                        adresse,
                        tel,
                        "client"
                );

                boolean success = Clientcontroleur.inscrireClient(nouveauClient);

                if (success) {
                    Session.setClient(nouveauClient);
                    dispose();
                    new Profil(nouveauClient);
                } else {
                    JOptionPane.showMessageDialog(this, "Erreur lors de l'inscription.", "Erreur", JOptionPane.ERROR_MESSAGE);
                }
            }
        });
    }

    private JPanel createInputField(String labelText, JComponent field) {
        JPanel panel = new JPanel();
        panel.setLayout(new BoxLayout(panel, BoxLayout.Y_AXIS));
        panel.setBackground(new Color(247, 247, 247));
        JLabel label = new JLabel(labelText);
        label.setFont(new Font("SansSerif", Font.PLAIN, 14));
        field.setAlignmentX(Component.LEFT_ALIGNMENT);
        field.setMaximumSize(new Dimension(Integer.MAX_VALUE, 35));
        panel.add(label);
        panel.add(Box.createVerticalStrut(5));
        panel.add(field);
        return panel;
    }

    private JLabel createNavLabel(String text) {
        JLabel label = new JLabel(text);
        label.setFont(new Font("SansSerif", Font.PLAIN, 14));
        label.setForeground(Color.BLACK);
        return label;
    }

    private JLabel createLinkLabel(String text, Runnable action) {
        JLabel label = new JLabel(text);
        label.setFont(new Font("SansSerif", Font.PLAIN, 13));
        label.setForeground(Color.BLACK);
        label.setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));
        label.setAlignmentX(Component.CENTER_ALIGNMENT);
        label.setBorder(BorderFactory.createEmptyBorder(10, 0, 10, 0));
        label.addMouseListener(new java.awt.event.MouseAdapter() {
            @Override
            public void mouseClicked(java.awt.event.MouseEvent e) {
                action.run();
            }
        });
        return label;
    }

    private JPanel createNavBar() {
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
        navRight.add(createNavLabel("👤"));
        navRight.add(createNavLabel("Panier"));
        navBar.add(navRight, BorderLayout.EAST);
        return navBar;
    }

    private JPanel createCategories() {
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
        return ligneMode;
    }

    public static void main(String[] args) {
        SwingUtilities.invokeLater(Inscription::new);
    }
}
