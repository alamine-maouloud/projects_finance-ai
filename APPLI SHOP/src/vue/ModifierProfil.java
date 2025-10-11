package Vue;

import Controleur.Clientcontroleur;
import Modele.Users.Client;

import javax.swing.*;
import java.awt.*;

public class ModifierProfil extends JFrame {

    private final Client client;
    private JTextField nomField, prenomField, emailField, adresseField, telField;

    public ModifierProfil(Client client) {
        this.client = client;

        setTitle("Modifier mes informations");
        setDefaultCloseOperation(DISPOSE_ON_CLOSE); // Ferme juste la popup
        setSize(400, 450);
        setLocationRelativeTo(null);
        setBackground(Color.WHITE);

        JPanel mainPanel = new JPanel();
        mainPanel.setLayout(new BoxLayout(mainPanel, BoxLayout.Y_AXIS));
        mainPanel.setBackground(Color.WHITE);
        mainPanel.setBorder(BorderFactory.createEmptyBorder(20, 30, 20, 30));

        JLabel titre = new JLabel("Modifier mes informations");
        titre.setFont(new Font("SansSerif", Font.BOLD, 18));
        titre.setAlignmentX(Component.CENTER_ALIGNMENT);
        titre.setBorder(BorderFactory.createEmptyBorder(10, 0, 20, 0));
        mainPanel.add(titre);

        // === CHAMPS ===
        nomField = createInputField("Nom", client.getLastName());
        prenomField = createInputField("Prénom", client.getFirstName());
        emailField = createInputField("Email", client.getEmail());
        adresseField = createInputField("Adresse", client.getAdress());
        telField = createInputField("Téléphone", client.getPhone());

        mainPanel.add(nomField);
        mainPanel.add(prenomField);
        mainPanel.add(emailField);
        mainPanel.add(adresseField);
        mainPanel.add(telField);

        mainPanel.add(Box.createVerticalStrut(20));

        // === Bouton ENREGISTRER ===
        JButton enregistrerButton = new JButton("Enregistrer");
        enregistrerButton.setBackground(Color.BLACK);
        enregistrerButton.setForeground(Color.WHITE);
        enregistrerButton.setFocusPainted(false);
        enregistrerButton.setFont(new Font("SansSerif", Font.BOLD, 14));
        enregistrerButton.setPreferredSize(new Dimension(120, 40));
        enregistrerButton.setAlignmentX(Component.CENTER_ALIGNMENT);

        mainPanel.add(enregistrerButton);

        // Action bouton enregistrer
        enregistrerButton.addActionListener(e -> enregistrerModifications());

        setContentPane(mainPanel);
        setVisible(true);
    }

    private JTextField createInputField(String placeholder, String value) {
        JTextField field = new JTextField(value);
        field.setMaximumSize(new Dimension(Integer.MAX_VALUE, 35));
        field.setAlignmentX(Component.LEFT_ALIGNMENT);
        field.setBorder(BorderFactory.createTitledBorder(placeholder));
        return field;
    }

    private void enregistrerModifications() {
        String nouveauNom = nomField.getText().trim();
        String nouveauPrenom = prenomField.getText().trim();
        String nouvelEmail = emailField.getText().trim();
        String nouvelleAdresse = adresseField.getText().trim();
        String nouveauTel = telField.getText().trim();

        if (nouveauNom.isEmpty() || nouveauPrenom.isEmpty() || nouvelEmail.isEmpty() || nouveauTel.isEmpty()) {
            JOptionPane.showMessageDialog(this, "Veuillez remplir tous les champs obligatoires.", "Erreur", JOptionPane.ERROR_MESSAGE);
            return;
        }

        // Mettre à jour le client local
        client.setLastName(nouveauNom);
        client.setFirstName(nouveauPrenom);
        client.setEmail(nouvelEmail);
        client.setAdress(nouvelleAdresse);
        client.setPhone(nouveauTel);

        // Mise à jour dans la base de données
        boolean success = Clientcontroleur.mettreAJourClient(client);

        if (success) {
            JOptionPane.showMessageDialog(this, "Informations mises à jour avec succès !");
            this.dispose();
            // Recharge la page profil
            SwingUtilities.invokeLater(() -> {
                JFrame topFrame = (JFrame) SwingUtilities.getWindowAncestor(this);
                if (topFrame != null) {
                    topFrame.dispose();
                }
                new Profil(client);
            });
        } else {
            JOptionPane.showMessageDialog(this, "Erreur lors de la mise à jour.", "Erreur", JOptionPane.ERROR_MESSAGE);
        }
    }
}
