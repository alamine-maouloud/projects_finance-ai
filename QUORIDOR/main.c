#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <windows.h>
#include <time.h>
#include <stdbool.h>
#define SIZE 9
#define ROWS (2 * SIZE - 1)
#define COLS (2 * SIZE - 1)
#define MAX_BARRIERS 20
#define MAX_PLAYERS 4
#define SCORE_FILE "scores.txt"
#define PARTIE_FILE "partie.txt"
#define JOUEURS_FILE "joueurs.txt"

typedef struct {
    char nom[100];
    char type; // type pour soit un humain soit une IA
    char jeton; // Jeton du joueur
    int mursRestants; // Nombre de barrières restantes
    int score; // Score du joueur
    /*int peutAnnuler; // Flag pour savoir si le joueur a déjà utilisé "Annuler l'action"*/
} Joueur;

typedef struct {
    int x;
    int y;
    /*char typeAction; // 'P' pour déplacement, 'B' pour barrière
    int x2; // Si c'est une barrière, l'autre extrémité (horizontal/vertical)
    int y2; // idem*/
} Action;

Action historiqueActions[100]; // Historique des actions effectuées
int historiqueIndex = 0;

void viderTampon() {
    int c;
    while ((c = getchar() != '\n' && c != EOF));
}

// Fonction pour choisir un joueur au hasard
int choisirJoueurAuHasard(int nombreJoueurs) {
    return rand() % nombreJoueurs;
}

// Fonction pour initialiser le générateur de nombres aléatoires
void initialiserAleatoire() {
    srand(time(NULL));  // Initialiser le générateur de nombres aléatoires avec l'heure actuelle
}

void Color(int couleurDuTexte, int couleurDeFond) {
    HANDLE H = GetStdHandle(STD_OUTPUT_HANDLE);
    SetConsoleTextAttribute(H, couleurDeFond * 16 + couleurDuTexte);
}

// Fonction pour charger les scores depuis un fichier
int chargerScores(Joueur joueur[], int *nombreScores) {
    FILE *fichier = fopen(SCORE_FILE, "r");
    if (!fichier) {
        return 0; // Aucun fichier n’existe encore
    }
    *nombreScores = 0;
    while (fscanf(fichier, "%s %d", joueur[*nombreScores].nom, &joueur[*nombreScores].score) == 2) {
        (*nombreScores)++;
    }

    fclose(fichier);
    return 1;
}

// Fonction pour sauvegarder les scores dans un fichier
void sauvegarderScores(Joueur joueur[], int nombreScores) {
    FILE *fichier = fopen(SCORE_FILE, "w");
    if (!fichier) {
        printf("Erreur : Impossible de sauvegarder les scores.\n");
        return;
    }

    for (int i = 0; i < nombreScores; i++) {
        fprintf(fichier, "%s %d\n", joueur[i].nom, joueur[i].score);
    }

    fclose(fichier);
}

// Fonction pour trouver un joueur existant dans les scores
int trouverJoueur(Joueur joueur[], int nombreScores, const char *nom) {
    for (int i = 0; i < nombreScores; i++) {
        if (strcmp(joueur[i].nom, nom) == 0) {
            return i;
        }
    }
    return -1; // Joueur non trouvé
}

// Fonction pour mettre à jour ou ajouter un score
void mettreAJourScore(Joueur joueur[], int *nombreScores, const char *nom, int points) {
    int index = trouverJoueur(joueur, *nombreScores, nom);

    if (index != -1) {
        joueur[index].score += points;
    } else {
        strcpy(joueur[*nombreScores].nom, nom);
        joueur[*nombreScores].score = points;
        (*nombreScores)++;
    }
}

// Fonction pour afficher les scores
void afficherScores(Joueur joueur[], int nombreScores) {
    system("cls");
    printf("\n=== SCORES DES JOUEURS ===\n");
    for (int i = 0; i < nombreScores; i++) {
        printf("%s : %d points\n", joueur[i].nom, joueur[i].score);
    }
    printf("===========================\n");
}

void afficherScoresDepuisFichier() {
    system("cls");
    FILE *fichier = fopen(SCORE_FILE, "r");
    if (fichier == NULL) {
        printf("╔═══════════════════════════════════════════╗\n");
        printf("║     Aucun score trouve                    ║\n");
        printf("║ Jouez une partie pour generer des scores. ║\n");
        printf("╚═══════════════════════════════════════════╝\n");
        return;
    }

    printf("╔════════════════════════════════════════╗\n");
    printf("║            SCORES DES JOUEURS          ║\n");
    printf("╠════════════════════════╦═══════════════╣\n");
    printf("║         Nom            ║     Points    ║\n");
    printf("╠════════════════════════╬═══════════════╣\n");

    char nom[100];
    int score;
    while (fscanf(fichier, "%s %d", nom, &score) == 2) {
        printf("║ %-22s ║ %-13d ║\n", nom, score);
    }

    printf("╚════════════════════════╩═══════════════╝\n");
    fclose(fichier);
    system("PAUSE");
}

// Fonction pour gérer les scores en fin de partie
void gestionScoresEnFinDePartie(Joueur joueurs[], int nombreJoueurs) {
    Joueur scoresSauvegardes[100];
    int nombreScores;

    // Charger les scores existants
    chargerScores(scoresSauvegardes, &nombreScores);

    // Mettre à jour les scores avec les résultats de la partie
    for (int i = 0; i < nombreJoueurs; i++) {
        mettreAJourScore(scoresSauvegardes, &nombreScores, joueurs[i].nom, joueurs[i].score);
    }

    // Sauvegarder les scores mis à jour
    sauvegarderScores(scoresSauvegardes, nombreScores);

    // Afficher les scores mis à jour
    afficherScores(scoresSauvegardes, nombreScores);
}

void afficherPlateauEtInfos(char plateau[ROWS][COLS], Joueur joueurs[], int nombreJoueurs, int joueurActif, int tour) {
    system("pause");
    system("cls");
    printf("\n");
    printf("");
    for (char c = 'A'; c < 'A' + SIZE; c++) {
        printf("    %c ", c);
    }
    printf("\n");

    for (int i = 0; i < ROWS; i++) {
        if (i % 2 == 0) {
            printf(" %d ", i / 2 + 1);
        } else {
            printf("   ");
        }

        for (int j = 0; j < COLS; j++) {
            if (i % 2 == 0 && j % 2 == 0) {
                Color(0, 15); // Couleur pour les cases principales
                printf(" %c ", plateau[i][j]);
            } else if (plateau[i][j] == 'B') {
                Color(0, 4); // Couleur pour les barrières
                printf(" %c ", plateau[i][j]);
            } else {
                Color(0, 8); // Couleur pour les espaces ou intersections
                printf("   ");
            }
            Color(15, 0); // Réinitialisation de la couleur
        }

        // Affichage des informations des joueurs
        if (i == 0) {
            printf("   Nombre de joueurs : %d", nombreJoueurs);
        } else if (i >= 2 && i < 2 + nombreJoueurs) {
            int idx = i - 2;
            // Affiche le joueur, son score, et ses murs restants
            printf("   Joueur %d : %s (Jeton : %c) | Murs restants : %d",
                   idx + 1, joueurs[idx].nom, joueurs[idx].jeton, joueurs[idx].mursRestants);

            // Indique si c'est le tour du joueur
            if (idx == joueurActif) {
                //printf(" < Tour en cours");
            }
        }

        printf("\n");
    }
    // Indication du joueur actif
    printf("\nC'est au tour de %s (Jeton : %c) de jouer.\n", joueurs[joueurActif].nom, joueurs[joueurActif].jeton);

    printf("\nActions possibles :\n");
    printf("1 - Deplacer son pion\n");
    printf("2 - Poser une barriere\n");
    printf("3 - Passer son tour\n");
    if (tour > 2) {
        printf("4 - Annuler la derniere action\n");
    } else {
        printf("4 - Annuler la derniere action (non disponible)\n");
    }
    printf("5 - Quitter le jeu\n");
}

void sauvpartie(char plateau[ROWS][COLS]) {
    FILE *fichier = fopen(PARTIE_FILE, "w");
    if (fichier == NULL) {
        printf("Erreur lors de l'ouverture du fichier");
        return;
    }
    for (int i = 0; i < ROWS; i++) {
        for (int j = 0; j < COLS; j++) {
            fprintf(fichier, "%c", plateau[i][j]);
        }
        fprintf(fichier, "\n"); //ajout d'une nouvelle ligne pour chaque ligne du plateau
    }
    fclose(fichier);
    printf("Partie sauvegarder avec succes. \n");
}

void reprise_partie(char plateau[ROWS][COLS], Joueur joueur[], int nombrejoueurs) {
    FILE *fichier = fopen(PARTIE_FILE, "r");
    if (fichier == NULL) {
        printf("Erreur lors de l'ouverture du fichier pour reprise. \n");
        return;
    }
    for (int i = 0; i < ROWS; i++) {
        for (int j = 0; j < COLS; j++) {
            printf("%c", plateau[i][j]);
            char c = fgetc(fichier); //lire un caractere
            if (c == '\n') c = fgetc(fichier); //ignorer les sauts de lignes
            if (c == EOF) {
                printf("erreur de lecture du fichier.\n");
                fclose(fichier);
                return;
            }
            plateau[i][j] = c;
        }
    }
    fclose(fichier);
    printf("Partie reprise avec succes.\n");
    afficherPlateauEtInfos(plateau, joueur, nombrejoueurs, 0, 1);
}

void sauvjoueurs(Joueur joueur[], int nombrejoueurs) {
    FILE *fichier = fopen(JOUEURS_FILE, "w");
    if (fichier == NULL) {
        printf("Erreur lors de l'ouverture du fichier pour sauv les joueurs.\n ");
        return;
    }
    for (int i = 0; i < nombrejoueurs; i++) {
        fprintf(fichier, "%s %c %d %d\n", joueur[i].nom, joueur[i].jeton, joueur[i].mursRestants, joueur[i].score);
    }
    fclose(fichier);
    printf("joueurs sauvegardes avec succes.\n");
}

void reprise_joueurs(Joueur joueur[], int *nombrejoueurs) {
    FILE *fichier = fopen(JOUEURS_FILE, "r");
    if (fichier == NULL) {
        printf("Erreur lors de l'ouverture du fichier pour sauv les joueurs.\n ");
        return;
    }
    *nombrejoueurs = 0;
    while (fscanf(fichier, "%s %c %d %d", joueur[*nombrejoueurs].nom, &joueur[*nombrejoueurs].jeton, &joueur[*nombrejoueurs].mursRestants, &joueur[*nombrejoueurs].score) == 4 ) {
        if (strlen(joueur[*nombrejoueurs].nom) == 0 || joueur[*nombrejoueurs].jeton == '\0') {
            printf("Erreur\n");
            fclose(fichier);
            return;
        }
        (*nombrejoueurs)++;
    }
    fclose(fichier);
    printf("Joueur repris avec succes.\n ");
}

void sauvegarderpartie(char plateau[ROWS][COLS], Joueur joueur[], int nombrejoueurs) {
    sauvpartie(plateau);
    sauvjoueurs(joueur, nombrejoueurs);
}

void reprendrepartie(char plateau[ROWS][COLS], Joueur joueur[], int *nombrejoueurs) {
    system("cls");
    // Initialisez les variables
    for (int i = 0; i < ROWS; i++) {
        for (int j = 0; j < COLS; j++) {
            plateau[i][j] = ' '; // Remplissez le plateau de cases vides
        }
    }

    *nombrejoueurs = 0; // Assurez-vous que le nombre de joueurs commence à 0

    // Reprenez les données du plateau
    reprise_partie(plateau, joueur, *nombrejoueurs);

    // Reprenez les données des joueurs
    reprise_joueurs(joueur, nombrejoueurs);

    // Vérifiez les données
    if (*nombrejoueurs <= 0 || *nombrejoueurs > MAX_PLAYERS) {
        printf("Erreur : données invalides lors de la reprise de la partie.\n");
        return;
    }

    printf("Partie reprise avec succès.\n");
    afficherPlateauEtInfos(plateau, joueur, *nombrejoueurs, 0, 1);
}

void initialiserPlateau(char plateau[ROWS][COLS], Joueur joueurs[], int nombreJoueurs) {
    for (int i = 0; i < ROWS; i++) {
        for (int j = 0; j < COLS; j++) {
            if (i % 2 == 0 && j % 2 == 0) {
                plateau[i][j] = ' ';
            } else {
                plateau[i][j] = '.';
            }
        }
    }

    if (nombreJoueurs == 2) {
        plateau[0][COLS / 2] = joueurs[0].jeton;
        plateau[ROWS - 1][COLS / 2] = joueurs[1].jeton;
    } else if (nombreJoueurs == 4) {
        plateau[0][COLS / 2] = joueurs[0].jeton;
        plateau[ROWS - 1][COLS / 2] = joueurs[1].jeton;
        plateau[ROWS / 2][0] = joueurs[2].jeton;
        plateau[ROWS / 2][COLS - 1] = joueurs[3].jeton;
    }
}

int verifierVictoire(char plateau[ROWS][COLS], Joueur joueurs[], int joueurActif, int nombreJoueurs) {
    if (nombreJoueurs == 2) {
        if (joueurActif == 0) {
            for (int j = 0; j < COLS; j += 2) {
                if (plateau[ROWS - 1][j] == joueurs[joueurActif].jeton) {
                    printf("\n==== %s a gagne la partie ! ====\n", joueurs[joueurActif].nom);
                    joueurs[joueurActif].score += 5;
                    gestionScoresEnFinDePartie(joueurs, nombreJoueurs);
                    return 1;
                }
            }
        } else if (joueurActif == 1) {
            for (int j = 0; j < COLS; j += 2) {
                if (plateau[0][j] == joueurs[joueurActif].jeton) {
                    printf("\n==== %s a gagne la partie ! ====\n", joueurs[joueurActif].nom);
                    joueurs[joueurActif].score += 5;
                    gestionScoresEnFinDePartie(joueurs, nombreJoueurs);
                    return 1;
                }
            }
        }
    }
    return 0; // Pas de victoire pour le moment
}

int validerDeplacement(int x1, int y1, int x2, int y2, char plateau[ROWS][COLS]) {
    // Vérification des barrières sur le chemin
    if (x1 == x2) { // Déplacement horizontal
        if (y2 > y1 && plateau[x1][y1 + 1] == 'B') { // Barrière à droite
            printf("Erreur : une barriere bloque le passage vers la droite.\n");
            return 0;
        }
        if (y2 < y1 && plateau[x1][y1 - 1] == 'B') { // Barrière à gauche
            printf("Erreur : une barriere bloque le passage vers la gauche.\n");
            return 0;
        }
    } else if (y1 == y2) { // Déplacement vertical
        if (x2 > x1 && plateau[x1 + 1][y1] == 'B') { // Barrière en bas
            printf("Erreur : une barriere bloque le passage vers le bas.\n");
            return 0;
        }
        if (x2 < x1 && plateau[x1 - 1][y1] == 'B') { // Barrière en haut
            printf("Erreur : une barriere bloque le passage vers le haut.\n");
            return 0;
        }
    }
    return 1; // Pas de barrière, déplacement valide
}

int deplacerPion(char plateau[ROWS][COLS], Joueur joueurs[], int joueurActif) {
    char direction[10];
    int x = 0, y = 0;

    // Trouver la position actuelle du pion
    for (int i = 0; i < ROWS; i++) {
        for (int j = 0; j < COLS; j++) {
            if (plateau[i][j] == joueurs[joueurActif].jeton) {
                x = i;
                y = j;
                break;
            }
        }
    }

    // Demander la direction jusqu'à un déplacement valide
    while (1) {
        printf("Deplacer le pion (%c) : h pour haut, b pour bas, g pour gauche, d pour droite: \n", joueurs[joueurActif].jeton);

        scanf("%s", direction);

        // Vérifier que la saisie est valide
        if (strlen(direction) != 1 ||
            (direction[0] != 'h' && direction[0] != 'b' && direction[0] != 'g' && direction[0] != 'd')) {
            printf("Erreur : veuillez entrer une seule lettre valide : 'h', 'b', 'g' ou 'd'.\n");
            continue;
        }

        int newX = x, newY = y;
        int jumpX = x, jumpY = y; // Pour gérer les sauts
        char dir = direction[0];

        // Calculer les nouvelles coordonnées sans saut
        if (dir == 'h') {
            newX -= 2; // Déplacement vers le haut
        } else if (dir == 'b') {
            newX += 2; // Déplacement vers le bas
        } else if (dir == 'g') {
            newY -= 2; // Déplacement vers la gauche
        } else if (dir == 'd') {
            newY += 2; // Déplacement vers la droite
        }

        // Vérifier si le déplacement est dans les limites du plateau
        if (newX < 0 || newX >= ROWS || newY < 0 || newY >= COLS) {
            printf("Deplacement invalide : hors des limites du plateau.\n");
            continue;
        }

        // Vérifier si un pion adverse est sur la case cible
        char adversaireJeton = joueurs[(joueurActif + 1) % 2].jeton;
        if (plateau[newX][newY] == adversaireJeton) {
            printf("Un pion adverse est detecte, saut en cours...\n");

             // Si c'est un mouvement vertical (haut / bas)
            if (dir == 'g' || dir == 'd') {
                // Vérifier s'il y a une barrière derrière le pion adverse verticalement
                int barrierX = newX;
                int barrierY = newY + (dir == 'd' ? 1 : -1); // Déplacer vers le bas ou le haut
                if (barrierX >= 0 && barrierX < ROWS && barrierY >= 0 && barrierY < COLS &&
                    plateau[barrierX][barrierY] == 'B') {
                    // Si une barrière est présente, demander une direction haut/bas
                    char choixSaut[10];
                    int validChoice = 0;

                    // Tant que l'utilisateur ne donne pas une entrée valide
                    while (!validChoice) {
                        printf("Une barriere est derriere le pion adverse. Voulez-vous sauter vers le haut ou vers le bas ? (h/b) : ");
                        fgets(choixSaut, sizeof(choixSaut), stdin); // Lire toute la ligne

                        // Enlever le '\n' éventuel à la fin
                        choixSaut[strcspn(choixSaut, "\n")] = '\0';

                        // Vérifier si l'entrée est valide
                        if (strlen(choixSaut) == 1 && (choixSaut[0] == 'h' || choixSaut[0] == 'b')) {
                            validChoice = 1; // Entrée valide
                        } else {
                            printf("entrer uniquement 'h' ou 'b'.\n");
                        }
                    }

                    // Appliquer la direction choisie
                    if (choixSaut[0] == 'h') {
                        jumpX = newX - 2;  // Se déplacer de 2 cases en haut
                        jumpY = newY;
                    } else if (choixSaut[0] == 'b') {
                        jumpX = newX + 2;  // Se déplacer de 2 cases en bas
                        jumpY = newY;
                    }
                } else {
                    /// Sauter directement derrière le pion adverse (dans la direction du mouvement)
                    if (dir == 'd') {
                        jumpX = newX;  // Rester sur la même ligne
                        jumpY = newY + 2;  // Avancer de 2 cases vers la droite
                    } else if (dir == 'g') {
                        jumpX = newX;  // Rester sur la même ligne
                        jumpY = newY - 2;  // Avancer de 2 cases vers la gauche
                    }
                }
            }
            // Si c'est un mouvement horizontal (gauche / droite)
            else if (dir == 'h' || dir == 'b') {
                // Vérifier s'il y a une barrière derrière le pion adverse horizontalement
                int barrierX = newX + (dir == 'b' ? 1 : -1); // Déplacer vers la droite ou la gauche
                int barrierY = newY;
                if (barrierX >= 0 && barrierX < ROWS && barrierY >= 0 && barrierY < COLS &&
                    plateau[barrierX][barrierY] == 'B') {
                    // Si une barrière est présente, demander une direction gauche/droite
                    char choixSaut[10];
                    int validChoice = 0;

                    // Tant que l'utilisateur ne donne pas une entrée valide
                    while (!validChoice) {
                        printf("Une barriere est derriere le pion adverse. Voulez-vous sauter vers la gauche ou la droite ? (g/d) : ");
                        fgets(choixSaut, sizeof(choixSaut), stdin); // Lire toute la ligne

                        // Enlever le '\n' éventuel à la fin
                        choixSaut[strcspn(choixSaut, "\n")] = '\0';

                        // Vérifier si l'entrée est valide
                        if (strlen(choixSaut) == 1 && (choixSaut[0] == 'g' || choixSaut[0] == 'd')) {
                            validChoice = 1; // Entrée valide
                        } else {
                            printf("entrer uniquement 'g' ou 'd'.\n");
                        }
                    }

                    // Appliquer la direction choisie
                    if (choixSaut[0] == 'g') {
                        jumpX = newX;
                        jumpY = newY - 2;  // Se déplacer de 2 cases à gauche
                    } else if (choixSaut[0] == 'd') {
                        jumpX = newX;
                        jumpY = newY + 2;  // Se déplacer de 2 cases à droite
                    }
                    } else {
                        if (dir == 'b') {
                            jumpX = newX + 2;  // Avancer de 2 cases vers le bas
                            jumpY = newY;  // Rester sur la même colonne
                        } else if (dir == 'h') {
                            jumpX = newX - 2;  // Avancer de 2 cases vers le haut
                            jumpY = newY;  // Rester sur la même colonne
                        }
                    }
            }
            // Vérifier si le saut est possible
            if (jumpX >= 0 && jumpX < ROWS && jumpY >= 0 && jumpY < COLS &&
                plateau[jumpX][jumpY] == ' ' && // Case après le saut est libre
                validerDeplacement(newX, newY, jumpX, jumpY, plateau)) {
                // Effectuer le saut
                plateau[jumpX][jumpY] = joueurs[joueurActif].jeton;
                plateau[x][y] = ' ';
                printf("Saut reussi vers (%d, %d).\n", jumpX, jumpY);
                return 1;
            } else {
                printf("Erreur : saut impossible, une barriere ou une limite bloque le passage.\n");
                continue;
            }
        }

        // Vérifier s'il n'y a pas de barrière bloquante pour un déplacement normal
        if (!validerDeplacement(x, y, newX, newY, plateau)) {
            continue; // Recommencer la saisie si une barrière bloque
        }

        // Vérifier si la case cible est libre pour un déplacement normal
        if (plateau[newX][newY] != ' ') {
            printf("Deplacement invalide : la case cible est occupee.\n");
            continue;
        }

        // Déplacer le pion pour un déplacement normal
        plateau[newX][newY] = joueurs[joueurActif].jeton;
        plateau[x][y] = ' ';
/*
        // Enregistrer l'action dans l'historique
        historiqueActions[historiqueIndex].typeAction = 'P'; // Type de l'action : déplacement
        historiqueActions[historiqueIndex].x = x;
        historiqueActions[historiqueIndex].y = y;
        historiqueActions[historiqueIndex].x2 = newX;
        historiqueActions[historiqueIndex].y2 = newY;
        historiqueIndex++;
*/
        return 1;
    }
}

int validerSaisieBarriere(char* saisie, int* x1, int* y1, int* x2, int* y2, char* direction) {
    // Vérifier la longueur totale de l'entrée
    if (strlen(saisie) != 7) {
        printf("Erreur : format incorrect. Veuillez entrer les deux cases voisines suivies de la direction (ex : D1 D2 G).\n");
        return 0;
    }

    // Vérifier que les espaces sont aux bons endroits
    if (saisie[2] != ' ' || saisie[5] != ' ') {
        printf("Erreur : la saisie doit etre sous ce format (ex: D5 D4 G).\n");
        return 0;
    }

    // Vérifier la structure des cases et la direction
    if ((saisie[0] < 'A' || saisie[0] > 'Z') ||  // Première lettre
        (saisie[1] < '1' || saisie[1] > '9') ||  // Premier chiffre
        (saisie[3] < 'A' || saisie[3] > 'Z') ||  // Deuxième lettre
        (saisie[4] < '1' || saisie[4] > '9') ||  // Deuxième chiffre
        (saisie[6] != 'H' && saisie[6] != 'B' && saisie[6] != 'D' && saisie[6] != 'G')) {  // Direction
        printf("Erreur : la saisie doit etre sous la forme 'C1 C2 D', avec des lettres et chiffres valides suivis d'une direction (H, B, D, G).\n");
        return 0;
        }

    // Extraire les composantes
    char case1[3] = {saisie[0], saisie[1], '\0'};
    char case2[3] = {saisie[3], saisie[4], '\0'};
    *direction = saisie[6];

    // Vérifier les cases (ex : D1, D2)
    if (case1[0] < 'A' || case1[0] >= 'A' + SIZE || case2[0] < 'A' || case2[0] >= 'A' + SIZE) {
        printf("Erreur : les lettres des cases doivent etre entre A et %c.\n", 'A' + SIZE - 1);
        return 0;
    }
    if (case1[1] < '1' || case1[1] >= '1' + SIZE || case2[1] < '1' || case2[1] >= '1' + SIZE) {
        printf("Erreur : les chiffres des cases doivent etre entre 1 et %d.\n", SIZE);
        return 0;
    }

    // Convertir les coordonnées en indices du tableau
    *x1 = (case1[1] - '1') * 2;
    *y1 = (case1[0] - 'A') * 2;
    *x2 = (case2[1] - '1') * 2;
    *y2 = (case2[0] - 'A') * 2;

    // Vérifier que les cases sont voisines
    if (!(abs(*x1 - *x2) == 2 && *y1 == *y2) && !(abs(*y1 - *y2) == 2 && *x1 == *x2)) {
        printf("Erreur : les cases doivent etre voisines horizontalement ou verticalement.\n");
        return 0;
    }

    // Vérification spécifique des lettres et chiffres en fonction de la direction
    if ((*direction == 'H' || *direction == 'B') && case1[0] == case2[0]) {
        printf("Erreur : impossible de mettre la barriere.\n");
        return 0;
    }
    if ((*direction == 'D' || *direction == 'G') && case1[1] == case2[1]) {
        printf("Erreur : impossible de mettre la barriere.\n");
        return 0;
    }

    // Vérifier que la barrière ne dépasse pas les limites du plateau
    if ((*x1 < 0 || *x1 >= ROWS || *y1 < 0 || *y1 >= COLS) ||
        (*x2 < 0 || *x2 >= ROWS || *y2 < 0 || *y2 >= COLS)) {
        printf("Erreur : la barriere depasse les limites du plateau.\n");
        return 0;
    }

    return 1;
}

int poserBarriere(char plateau[ROWS][COLS], Joueur joueurs[], int joueurActif) {
    if (joueurs[joueurActif].mursRestants <= 0) {
        printf("Vous n'avez plus de barrieres disponibles.\n");
        return 0;
    }

    char saisie[10];
    int x1, y1, x2, y2;
    char direction;

    while (1) {
        printf("%s, entrez la position de la barriere que vous voulez poser (ex : D1 D2 G) : ", joueurs[joueurActif].nom);
        scanf(" %[^\n]", saisie);

        if (validerSaisieBarriere(saisie, &x1, &y1, &x2, &y2, &direction)) {
            // Vérification selon la direction et la règle spécifique
            if (direction == 'H') {
                if (x1 - 1 < 0 || plateau[x1 - 1][y1] == 'B' || plateau[x2 - 1][y2] == 'B' ||
                    plateau[x1 - 1][y1] == ' ') { // Règle : pas de case blanche
                    printf("Erreur : emplacement invalide pour une barriere horizontale.\n");
                    continue;
                }
                plateau[x1 - 1][y1] = 'B';
                plateau[x2 - 1][y2] = 'B';
            } else if (direction == 'B') {
                if (x1 + 1 >= ROWS || plateau[x1 + 1][y1] == 'B' || plateau[x2 + 1][y2] == 'B' ||
                    plateau[x1 + 1][y1] == ' ') { // Règle : pas de case blanche
                    printf("Erreur : emplacement invalide pour une barriere verticale basse.\n");
                    continue;
                }
                plateau[x1 + 1][y1] = 'B';
                plateau[x2 + 1][y2] = 'B';
            } else if (direction == 'G') {
                if (y1 - 1 < 0 || plateau[x1][y1 - 1] == 'B' || plateau[x2][y2 - 1] == 'B' ||
                    plateau[x1][y1 - 1] == ' ') { // Règle : pas de case blanche
                    printf("Erreur : emplacement invalide pour une barriere gauche.\n");
                    continue;
                }
                plateau[x1][y1 - 1] = 'B';
                plateau[x2][y2 - 1] = 'B';
            } else if (direction == 'D') {
                if (y1 + 1 >= COLS || plateau[x1][y1 + 1] == 'B' || plateau[x2][y2 + 1] == 'B' ||
                    plateau[x1][y1 + 1] == ' ') { // Règle : pas de case blanche
                    printf("Erreur : emplacement invalide pour une barriere droite.\n");
                    continue;
                }
                plateau[x1][y1 + 1] = 'B';
                plateau[x2][y2 + 1] = 'B';
            } else {
                printf("Erreur : direction invalide.\n");
                continue;
            }
/*
            // Enregistrer l'action dans l'historique
            historiqueActions[historiqueIndex].typeAction = 'B'; // Type de l'action : barrière
            historiqueActions[historiqueIndex].x = x1;
            historiqueActions[historiqueIndex].y = y1;
            historiqueActions[historiqueIndex].x2 = x2;
            historiqueActions[historiqueIndex].y2 = y2;
            historiqueIndex++;
*/
            // Réduction des murs restants pour ce joueur
            joueurs[joueurActif].mursRestants--;

            printf("%s a place une barriere avec succes !\n", joueurs[joueurActif].nom);
            return 1;
        }

        printf("Saisie incorrecte. Veuillez reessayer.\n");
    }
}

/*void annulerAction(char plateau[ROWS][COLS], Joueur joueurs[], int joueurActif, int nombreJoueurs, int tour) {
    // Vérification de l'utilisation unique
    if (joueurs[joueurActif].peutAnnuler == 0) {
        printf("Vous avez déjà utilisé l'option 'Annuler une action'.\n");
        return;
    }

    // Vérifier si l'annulation est possible en fonction du nombre de joueurs et du tour
    if ((nombreJoueurs == 2 && tour < 3) || (nombreJoueurs == 4 && tour < 5)) {
        printf("L'annulation d'action n'est pas disponible avant 2 tours (pour 2 joueurs) ou 4 tours (pour 4 joueurs).\n");
        return;
    }

    // Calcul du nombre de tours à annuler
    int toursAnnuler = (nombreJoueurs == 2) ? 2 : 4;
    int actionAnnulerIndex = historiqueIndex - toursAnnuler;

    if (actionAnnulerIndex < 0) {
        printf("Il n'y a pas suffisamment d'actions pour annuler.\n");
        return;
    }

    // Annulation des actions jusqu'à l'index calculé
    for (int i = historiqueIndex - 1; i >= actionAnnulerIndex; i--) {
        Action a = historiqueActions[i];
        if (a.typeAction == 'P') {
            // Annuler un déplacement de pion
            plateau[a.x][a.y] = ' '; // Réinitialisation de la position précédente
            plateau[a.x2][a.y2] = joueurs[joueurActif].jeton; // Replacer le pion à son ancienne position
        } else if (a.typeAction == 'B') {
            // Annuler une barrière
            plateau[a.x][a.y] = ' '; // Enlever la première partie de la barrière
            plateau[a.x2][a.y2] = ' '; // Enlever la deuxième partie de la barrière
        }
    }

    // Réinitialiser l'historique jusqu'à l'action annulée
    historiqueIndex = actionAnnulerIndex;

    // Indiquer que le joueur a utilisé cette option
    joueurs[joueurActif].peutAnnuler = 0;

    printf("L'action a été annulée. Vous pouvez rejouer.\n");
}*/

void passerSonTour(int joueurActif, int nombreJoueurs) {
    // Cette fonction ne fait rien, le joueur actif garde son tour, mais aucune action n'est réalisée
    printf("Vous avez choisi de passer votre tour.\n");
}

void lancerNouvellePartie() {
    system("cls");
    char plateau[ROWS][COLS];
    Joueur joueurs[MAX_PLAYERS];
    int nombreJoueurs, tour = 1, joueurActif = 0;
    char buffer[10]; // Utilisé pour lire les entrées utilisateur
    int victoire = 0; //Variable pour indiquer si une victoire a eu lieu
    // Initialisation des nombres aléatoires
    initialiserAleatoire();

    // Blindage pour le choix du nombre de joueurs
    do {
        printf("Nombre de joueurs (2 ou 4): \n");
        scanf("%s", buffer); // On lit une chaîne pour capturer n'importe quelle entrée
        if (strlen(buffer) == 1 && (buffer[0] == '2' || buffer[0] == '4')) {
            nombreJoueurs = buffer[0] - '0'; // Conversion en entier
        } else {
            printf("Erreur : entrer 2 ou 4 uniquement. Reessayez.\n");
        }
    } while (nombreJoueurs != 2 && nombreJoueurs != 4);

    for (int i = 0; i < nombreJoueurs; i++) {
        printf("\nJoueur %d :\n", i + 1);
        do {
            printf("Nom: \n");
            scanf("%s", joueurs[i].nom);
            int valide = 1;
            for (int j = 0; j < strlen(joueurs[i].nom); j++) {
                if (!isalpha(joueurs[i].nom[j])) {
                    valide = 0;
                    break;
                }
            }
            if (!valide) {
                printf("Le nom ne doit contenir une chaine de caractere. Veuillez reessayer.\n");
            } else {
                break;
            }
        } while (1);

        // Saisie et vérification du type de joueur
        do {
            printf("Type (H pour Humain, I pour IA): \n");
            scanf("%s", buffer); // Lecture de l'entrée comme chaîne
            if (strlen(buffer) == 1 && (buffer[0] == 'H' || buffer[0] == 'I')) {
                joueurs[i].type = buffer[0]; // Assigner la valeur si valide
            } else {
                printf("Erreur : entrer uniquement 'H' pour Humain ou 'I' pour IA. Reessayez.\n");
            }
        } while (joueurs[i].type != 'H' && joueurs[i].type != 'I');

        // Demander le pion du joueur
        char pion;
        int pionValide;
        do {
            pionValide = 1; // Réinitialisation de la validité
            printf("Choisissez un pion : \n");
            scanf("%s", buffer);

            // Vérifier si l'utilisateur a entré plus d'un caractère
            if (strlen(buffer) != 1) {
                printf("Erreur : vous devez entrer UN seul caractere. Veuillez reessayer.\n");
                pionValide = 0;
                continue;
            }

            // Vérifier si le pion est déjà pris
            for (int j = 0; j < i; j++) {
                if (joueurs[j].jeton == buffer[0]) {
                    printf("Ce pion est deja pris. Veuillez en choisir un autre.\n");
                    pionValide = 0;
                    break;
                }
            }
        } while (!pionValide);

        joueurs[i].jeton = buffer[0]; // Assigner le pion choisi
        joueurs[i].mursRestants = MAX_BARRIERS / nombreJoueurs;
        joueurs[i].score = 0;
        printf("Votre pion sera '%c'.\n", joueurs[i].jeton);
    }

    // Choisir aléatoirement le joueur qui commence
    joueurActif = choisirJoueurAuHasard(nombreJoueurs);

    initialiserPlateau(plateau, joueurs, nombreJoueurs);
    // Afficher le message "=== Début de la Partie ===" avant le premier tour
    printf("=== Debut de la Partie ===\n");

    while (1) {
        //system("cls");
        afficherPlateauEtInfos(plateau, joueurs, nombreJoueurs, joueurActif, tour);
        //printf("\nChoisissez une action (1, 2, 3 ou 4): \n");
        char input[10]; // Tampon pour l'entrée utilisateur
        int action = 0;

        while (!victoire) {
            printf("Votre choix : ");
            if (fgets(input, sizeof(input), stdin) == NULL) {
                printf("Erreur lors de la lecture. Veuillez reessayer.\n");
                continue;
            }

            // Vérifier si l'entrée est vide (juste un appui sur Entrée)
            if (input[0] == '\n') {
                printf("entrer un nombre entre 1 et 5 \n");
                continue;
            }

            // Tenter de convertir l'entrée en entier
            char *endptr;
            action = strtol(input, &endptr, 10);

            // Vérifier qu'il n'y a que des chiffres valides
            if (*endptr != '\n' && *endptr != '\0') {
                printf("Entree invalide. Veuillez entrer un nombre entre 1 et 5 :\n");
                continue;
            }

            // Vérifier que le nombre est dans la plage valide
            if (action < 1 || action > 5) {
                printf("Entree invalide. Veuillez entrer un nombre entre 1 et 5 :\n");
                continue;
            }

            // Si tout est valide, sortir de la boucle
            break;
        }

        if (action == 4 && tour == 1) {
            printf("Annulation impossible au premier tour. Reessayez.\n");
            system("pause");
            continue;
        }

        if (action == 1) {
            if (deplacerPion(plateau, joueurs, joueurActif)) {
                if(verifierVictoire(plateau, joueurs, joueurActif, nombreJoueurs)) {
                    victoire = 1;
                    break;
                }
                Action nouvelleAction = {0}; // Déplacement de pion
                historiqueActions[historiqueIndex++] = nouvelleAction;
            }
        } else if (action == 2) {
            if (poserBarriere(plateau, joueurs, joueurActif)) {
                Action nouvelleAction = {1}; // Pose de barrière
                historiqueActions[historiqueIndex++] = nouvelleAction;
            }
        } else if (action == 3) {
            passerSonTour(joueurActif, nombreJoueurs);
        } else if (action == 4) {
            /*if (tour > 2) {
                // Appeler la fonction pour annuler l'action précédente
                annulerAction(plateau, joueurs, joueurActif, nombreJoueurs, tour);
            } else {
                printf("L'annulation n'est pas disponible au début du jeu.\n");
            }*/
        }
        if (action == 5) {
            printf("Voulez-vous sauvegarder la partie avant de quitter ? (O : pour oui, N : pour non)\n");
            char reponse;
            if (scanf(" %c", &reponse) != 1) {
                printf("Erreur de lecture. Retour au menu principal.\n");
                continue;
            }
            if (reponse == 'O' || reponse == 'o') {
                sauvegarderpartie(plateau, joueurs, nombreJoueurs);
                printf("Partie sauvegardée avec succès. Au revoir !\n");
                break;
            } else {
                printf("Vous avez choisi de ne pas sauvegarder. Au revoir !\n");
                break;
            }
        }
        tour++;
        joueurActif = (joueurActif + 1) % nombreJoueurs;
    }
    printf("Partie terminee. Merci d'avoir joue !\n");
}

void continuer_partie(char plateau[ROWS][COLS], Joueur joueur[], int nombrejoueurs) {
    system("cls");
    int joueurActif = 0;
    int tour = 1;
    int victoire = 0;

    printf("=== Reprise de la partie ===\n");
    while (!victoire) {
        afficherPlateauEtInfos(plateau, joueur, nombrejoueurs, joueurActif, tour);
        printf("\nChoisissez une action (1, 2, 3, 4 ou 5): \n");
        int action;
        scanf("%d", &action);
        viderTampon();
        if (action == 1) {
            if (deplacerPion(plateau, joueur, joueurActif)) {
                if (verifierVictoire(plateau, joueur, joueurActif, nombrejoueurs)) {
                    victoire = 1; // Marquer la victoire
                    break;       // Quitter la boucle si un joueur gagne
                }
            }
        } else if (action == 2) {
            poserBarriere(plateau, joueur, joueurActif);
        } else if (action == 3) {
            joueurActif = (joueurActif + 1) % nombrejoueurs;
        } else if (action == 4 && tour > 1) {
            //annulerDerniereAction(plateau, joueur, historiqueActions, &historiqueIndex);
        } else if (action == 5) {
            printf("Vous avez quitté la partie.\n");
            break;
        }

        tour++;
        joueurActif = (joueurActif + 1) % nombrejoueurs;
    }
}

void afficherAide() {
    system("cls"); // Efface l'écran pour une meilleure lisibilité

    printf("╔══════════════════════════════════════════════════════════════╗\n");
    printf("║                    AIDE DU JEU QUORIDOR                      ║\n");
    printf("╚══════════════════════════════════════════════════════════════╝\n\n");

    printf("Quoridor est un jeu de strategie pour 2 ou 4 joueurs.\n");
    printf("Le but du jeu est d'atteindre la ligne opposee du plateau avant vos adversaires.\n\n");

    printf("╔═════════════════════════════ REGLES DU JEU ═════════════════════╗\n");
    printf("║ 1. Chaque joueur commence avec un pion place sur le plateau     ║\n");
    printf("║    et un nombre fixe de barrieres.                              ║\n");
    printf("║ 2. A votre tour, vous pouvez :                                  ║\n");
    printf("║    - Deplacer votre pion d'une case dans une direction valide   ║\n");
    printf("║      (haut, bas, gauche ou droite).                             ║\n");
    printf("║    - Placer une barriere pour bloquer vos adversaires.          ║\n");
    printf("║ 3. Les deplacements sont limites aux cases adjacentes           ║\n");
    printf("║    et ne doivent pas traverser de barrieres.                    ║\n");
    printf("║ 4. Les barrieres ne peuvent pas completement bloquer un joueur. ║\n");
    printf("║    Chaque joueur doit toujours avoir un chemin possible         ║\n");
    printf("║    vers son objectif.                                           ║\n");
    printf("╚═════════════════════════════════════════════════════════════════╝\n\n");

    printf("╔═════════════════════════════ COMMANDES ═════════════════════════╗\n");
    printf("║ 1. Deplacer le pion : Choisissez une direction                  ║\n");
    printf("║    (h: haut, b: bas, g: gauche, d: droite).                     ║\n");
    printf("║ 2. Poser une barriere : Indiquez deux cases voisines            ║\n");
    printf("║    et la direction de la barriere.                              ║\n");
    printf("║ 3. Annuler une action (si disponible).                          ║\n");
    printf("║ 4. Passer votre tour (dans des cas speciaux).                   ║\n");
    printf("╚═════════════════════════════════════════════════════════════════╝\n\n");

    printf("╔═════════════════════════════ CONSEILS ══════════════════════════╗\n");
    printf("║ 1. Utilisez vos barrieres strategiquement pour ralentir         ║\n");
    printf("║    vos adversaires sans bloquer votre propre chemin.            ║\n");
    printf("║ 2. Analysez les mouvements de vos adversaires pour anticiper    ║\n");
    printf("║    leurs strategies.                                            ║\n");
    printf("║ 3. Pensez a conserver quelques barrieres pour les derniers      ║\n");
    printf("║    tours.                                                       ║\n");
    printf("╚═════════════════════════════════════════════════════════════════╝\n\n");

    printf("Appuyez sur une touche pour revenir au menu principal.\n");
    system("pause"); // Attendre une action de l'utilisateur avant de revenir au menu
}

void afficherMenu() {
    int choix;
    char buffer[10];
    int nombrejoueurs;
    char plateau[ROWS][COLS];
    Joueur joueur[MAX_PLAYERS];

    while (choix != 5) {
        system("cls"); // Efface l'écran pour une meilleure lisibilité
        printf("╔══════════════════════════════════════╗\n");
        printf("║             MENU PRINCIPAL           ║\n");
        printf("╠══════════════════════════════════════╣\n");
        printf("║ 1. Lancer une nouvelle partie        ║\n");
        printf("║ 2. Reprendre une partie sauvegardée  ║\n");
        printf("║ 3. Afficher l'aide                   ║\n");
        printf("║ 4. Afficher les scores des joueurs   ║\n");
        printf("║ 5. Quitter le jeu                    ║\n");
        printf("╚══════════════════════════════════════╝\n");
        printf("Votre choix: ");

        scanf("%s", buffer); // Lecture de l'entrée utilisateur comme chaîne
        viderTampon();

        if (strlen(buffer) == 1 && buffer[0] >= '1' && buffer[0] <= '5') {
            choix = buffer[0] - '0'; // Conversion en entier si valide
        } else {
            printf("Erreur : entrer un nombre entre 1 et 5.\n");
            system("pause"); // Attendre avant de redessiner le menu
            continue;
        }

        switch (choix) {
            case 1:
                system("cls");
                lancerNouvellePartie();
                break;
            case 2:
                system("cls");
                reprendrepartie(plateau, joueur, &nombrejoueurs);
                if (nombrejoueurs > 0) {
                    continuer_partie(plateau, joueur, nombrejoueurs);
                } else {
                    printf("Impossible de reprendre la partie. Aucune donnée trouvée.\n");
                    system("pause");
                }
                break;
            case 3:
                afficherAide();
                break;
            case 4:
                afficherScoresDepuisFichier();
                system("pause");
                break;
            case 5:
                system("cls");
                printf("╔══════════════════════════════════════╗\n");
                printf("║       Vous avez quitté le jeu.       ║\n");
                printf("║              Au revoir !             ║\n");
                printf("╚══════════════════════════════════════╝\n");
                break;
            default:
                printf("Veuillez réessayer.\n");
                system("pause");
                break;
        }
    }
}

int main() {

    SetConsoleOutputCP(CP_UTF8);
    system("cls");
    Color(10, 0);
    printf("==== BIENVENUE SUR LE JEU QUORIDOR ====\n");
    Color(9, 0);
    afficherMenu();

    return 0;
}
