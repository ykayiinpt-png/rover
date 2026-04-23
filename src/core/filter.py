from scipy.signal import butter, lfilter_zi, lfilter

class LowPassFilter2ndOrder:
    """
    Filtre passe-bas IIR numérique 2ème ordre réutilisable.
    """

    def __init__(self, cutoff_freq, fs, order=2, initial_value=0.0):
        """
        :param cutoff_freq: fréquence de coupure en Hz
        :param fs: fréquence d'échantillonnage en Hz
        :param order: ordre du filtre (défaut 2)
        :param initial_value: valeur initiale du filtre pour un démarrage stable
        """
        self.cutoff_freq = cutoff_freq
        self.fs = fs
        self.order = order
        
        # Coefficients du filtre
        self.b, self.a = butter(order, cutoff_freq / (0.5 * fs), btype='low', analog=False)
        
        # État interne du filtre pour l'application temps réel
        self.zi = lfilter_zi(self.b, self.a) * initial_value
        
        # Dernière valeur filtrée
        self.last = initial_value

    def update(self, value):
        """
        Met à jour le filtre avec une nouvelle donnée et retourne la valeur filtrée.
        :param value: nouvelle donnée
        :return: valeur filtrée
        """
        filtered, self.zi = lfilter(self.b, self.a, [value], zi=self.zi)
        self.last = filtered[0]
        return self.last

    def get(self):
        """Retourne la dernière valeur filtrée"""
        return self.last