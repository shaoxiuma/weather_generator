#!/usr/bin/env python
"""
AWAP weather generator functions
- testing before writing them in C for GDAY
"""

import sys
import numpy as np
import matplotlib.pyplot as plt
from math import pi, cos, sin, exp, sqrt, acos
import random

__author__  = "Martin De Kauwe"
__version__ = "1.0 (16.03.2016)"
__email__   = "mdekauwe@gmail.com"


def main():

    tmin = 2.0
    tmax = 24.0
    doy = 180.0
    sw_rad_day = 50.0 # mj
    sw_rad_wm2 = sw_rad_day / 0.0864
    lat = 51.5
    lon = -0.13
    hours = np.arange(48) / 2.0

    (par, day_length) = estimate_dirunal_par(lat, doy, sw_rad_day)

    (elevation, cos_zenith) = calculate_solar_geometry(doy, lat, lon)
    (direct_frac, diffuse_frac) = spitters(doy, sw_rad_wm2, cos_zenith)

    fig, ax1 = plt.subplots()
    ax2 = ax1.twinx()
    ax1.plot(hours, elevation, "g-", label="elevation")
    ax2.plot(hours, diffuse_frac, "r-", label="Diffuse")
    ax2.plot(hours, direct_frac, "b-", label="Direct")
    plt.legend(numpoints=1, loc="best")
    plt.show()

    plt.plot(hours, par, "r-")
    plt.ylabel("par ($\mu$mol m$^{-2}$ s$^{-1}$)")
    plt.xlabel("Hour of day")
    plt.show()

    tday = estimate_diurnal_temp(tmin, tmax, day_length)
    tday2 = maestra_diurnal_func(tmin, tmax, day_length)

    plt.plot(hours, tday, "r-", label="Parton & Logan")
    plt.plot(hours, tday2, "k-", label="MAESPA")
    plt.legend(numpoints=1, loc="best")
    plt.ylabel("Air Temperature (deg C)")
    plt.xlabel("Hour of day")
    plt.show()

    sys.exit()

    rain = 10.0
    ppt = disaggregate_rainfall(rain)
    plt.plot(hours, ppt, "ro")
    plt.ylabel("PPT (mm)")
    plt.xlabel("Hour of day")
    plt.ylim(0, 3)
    plt.show()

    vpd09 = 1.4
    vpd09_next = 1.8
    vpd15 = 2.3
    vpd15_prev = 3.4
    vpd = estimate_diurnal_vpd(vpd09, vpd15, vpd09_next, vpd15_prev)

    plt.plot(hours, vpd, "ro")
    plt.ylabel("VPD (kPa)")
    plt.xlabel("Hour of day")
    plt.ylim(0, 3)
    plt.show()


def estimate_dirunal_par(lat, doy, sw_rad_day):

    sec_2_day = 86400.0
    day_2_hour = 1.0 / 24.0
    SW_2_PAR = 2.3

    # Solar constant [MJ/m2/day]
    solar_constant = 1370.0 * sec_2_day / 1E6

    # convert to radians
    rlat  = lat * np.pi / 180.0
    ryear = 2.0 * np.pi * (doy - 1.0) / 365.0

    # Declination in radians (Paltridge and Platt eq [3.7])
    rdec = (0.006918 - 0.399912 * np.cos(ryear) + 0.070257 *
            np.sin(ryear) - 0.006758 * np.cos(2.0 * ryear) +
            0.000907 * np.sin(2.0 * ryear) - 0.002697 *
            np.cos(3.0  *ryear) + 0.001480 * np.sin(3.0 * ryear))

    # Declination in degrees
    dec = (180.0 / np.pi) * rdec

    hour_angle = -np.tan(rlat) * np.tan(rdec)

    # Half Day Length (radians), (dawn:noon = noon:dusk)
    # Paltridge and Platt eq [3.21]
    if hour_angle <= -1.0:
        rhlf_day_length = np.pi            # polar summer: sun never sets
    elif hour_angle >= 1.0:
        rhlf_day_length = 0.0              # polar winter: sun never rises
    else:
        rhlf_day_length = np.arccos(hour_angle)

    # hrs
    day_length = 24.0 * 2.0 * rhlf_day_length / (2.0 * np.pi)

    # Daily solar irradiance without atmosphere, normalised by solar constant,
    # with both energy fluxes in MJ/m2/day, calculated from solar geometry
    # Paltridge and Platt eq [3.22]
    solar_norm = (rhlf_day_length * np.sin(rlat) * np.sin(rdec) +
                  np.cos(rlat) * np.cos(rdec) * np.sin(rhlf_day_length)) / np.pi

    # Observed daily solar irradiance as frac of value from solar geometry
    # (should be < 1), sw_rad (MJ m-2 d-1)
    solar_frac_obs = sw_rad_day / (solar_norm * solar_constant + 1.0E-6)

    sw_rad = np.zeros(48)

    # disaggregate radiation
    for i in xrange(1,48+1):

        hour = i / 2.0

        # Time in day frac (-0.5 to 0.5, zero at noon)
        time_noon = float(hour) / 24.0 - 0.5

        # Time in day frac (-Pi to Pi, zero at noon)
        rtime = 2.0 * np.pi * time_noon

        #print hour, time_noon, rtime
        if (np.abs(rtime) < rhlf_day_length): # day: sun is up
            # Paltridge and Platt eq [3.4]
            sw_rad[i-1] = ((sw_rad_day / solar_norm) * (np.sin(rdec) *
                          np.sin(rlat) + np.cos(rdec) * np.cos(rlat) *
                          np.cos(rtime)))

            # Need to half rad, as we are doing this over 48 timesteps and not
            # 24, otherwise we will end up with a total which is double
            # the sw_rad_tot
            sw_rad[i-1] /= 2.0
        else:
            sw_rad[i-1] = 0.0

    # integrated solar will be too high as we are using a limited number of
    # timseteps, so we need to figure out how wrong and correct things
    solar_extra = sw_rad_day - (np.sum(sw_rad) * day_2_hour)
    #print solar_extra

    # Convert sw_rad (MJ/m2/day to W/m2) to PAR (umol m-2 s-1)
    par = sw_rad * 1E6 / sec_2_day * SW_2_PAR

    return (par, day_length)

def estimate_diurnal_vpd(vpd09, vpd15, vpd09_next, vpd15_prev):
    """
    Interpolate VPD between 9am and 3pm values to generate diurnal VPD
    following the method of Haverd et al. This seems reasonable, vapour pressure
    plotted aginst time of day often does not reveal consistent patterns, with
    small fluctuations (see Kimball and Bellamy, 1986).

    Reference:
    ---------
    * Haverd et al. (2013) Multiple observation types reduce uncertainty in
      Australia's terrestrial carbon and water cycles. Biogeosciences, 10,
      2011-2040.
    """
    # number of hours gap, i.e. 3pm to 9am the next day
    gap = 18.0

    vpd = np.zeros(48)
    for i in xrange(1, 48+1):
        hour = i / 2.0
        if hour <= 9.0:
           vpd[i-1] = vpd15_prev + (vpd09 - vpd15_prev) * (9.0 + hour) / gap
        elif hour > 9.0 and hour <= 15.0:
           vpd[i-1] = vpd09 + (vpd15 - vpd09) * (hour - 9.0) / (15.0 - 9.0)
        elif hour > 15.0:
            vpd[i-1] =  vpd15 + (vpd09_next - vpd15) * (hour - 15.0) / gap

    return vpd

def disaggregate_rainfall(rain):
    """
    Assign daily PPT total to hours of the day, following MAESTRA, which follows
    algorithm from GRAECO (model of D. Loustau).

    Reference:
    * Loustau, D., F. Pluviaud, A. Bosc, A. Porte, P. Berbigier, M. Deque
      and V. Perarnaud. 2001. Impact of a regional 2 x CO2 climate scenario
      on the water balance, carbon balance and primary production
      of maritime pine in southwestern France. In Models for the Sustainable
      Management of Plantation Forests. Ed. M. Tome. European
      Cultivated Forest Inst., EFI Proc. No. 41D, Bordeaux, pp 45-58.
    """
    ppt = np.zeros(48)

    # All rain falls in one hour for light storms (<2 mm)
    if rain <= 2.0:
        hour_index = np.random.randint(low=0, high=47)
        ppt[hour_index] = rain

    # All rain falls in 24 hours for storms >46 mm
    elif rain > 46.0:
        for i in xrange(48):
            ppt[i] = rain / 48.0

    # Aim if for all rain to fall at 2mm/hour at a random time of the day.
    # If we generate the same random number, then we increase rainfall
    # for this hour
    else:
        #num_hrs_with_rain = min(int((rain / 2.0) * 48. / 24.), 48)
        num_hrs_with_rain = int(rain / 2.0)
        rate = rain / float(num_hrs_with_rain)
        # sample without replacement
        #random_hours = random.sample(range(0, 48), num_hrs_with_rain)
        random_hours = np.random.randint(low=0, high=47, size=num_hrs_with_rain)
        print random_hours
        for i in xrange(num_hrs_with_rain):
            ppt[random_hours[i]] += rate

    return ppt

def maestra_diurnal_func(tmin, tmax, day_length):
    """ Not sure where this function original comes from... """
    tav = (tmax + tmin) / 2.0
    tampl = (tmax - tmin) / 2.0

    dayl = day_length * 2.

    tday = np.zeros(48)
    for i in xrange(1, 48+1):
        hrtime = i - 0.5
        time = i + dayl * 0.5 - 48.0 / 2.0
        if time < 0.0 or time > dayl:
            if time < 0.0:
                hrtime += 48

            arg1 = tav
            arg2 = (tav - tmin) * (hrtime - dayl * 0.5 - (48.0 / 2.0))
            arg3 = 48.0 - dayl

            tday[i-1] = arg1 - arg2 / arg3
        else:
            tday[i-1] = tav - tampl * cos(1.5 * pi * time / dayl)

    return (tday)

def estimate_diurnal_temp(tmin, tmax, day_length):
    """
    Calculate diurnal temperature following Parton and Logan
    the day is divided into two segments and using a truncated sine wave
    in the daylight and an exponential decrease in temperature
    at night.

    TO DO:
    - Hours between 00:00 and sunrise should be modelled using the previous
      days information.

    References:
    ----------
    * Parton and Logan (1981) A model for dirunal variation in soil and
       air temperature. Agricultural Meteorology, 23, 205--216.
    * Kimball and Bellamy (1986) Energy in Agriculture, 5, 185-197.
    """
    # 1.5 m air temperature values from Parton and Logan, table 1
    a = 1.86
    b = 2.2     # nighttime coeffcient
    c = -0.17   # lag of the min temp from the time of runrise


    night_length = 24 - day_length

    sunrise = 12.0 - day_length / 2.0 + c
    sunset = 12.0 + day_length / 2.0

    # temperature at sunset
    m = sunset - sunrise + c
    tset = (tmax - tmin) * sin(pi * m / (day_length + 2.0 * a)) + tmin

    tday = np.zeros(48)
    for i in xrange(1, 48+1):
        hour = i / 2.0

        # hour - time of the minimum temperature (accounting for lag time)
        m = hour - sunrise + c
        if hour >= sunrise and hour <= sunset:
            tday[i-1] = tmin + (tmax - tmin) * \
                        sin((pi * m) / (day_length + 2.0 * a))
        else:
            if hour > sunset:
                n = hour - sunset
            elif hour < sunrise:
                n = (24.0 + hour) - sunset


            d = (tset - tmin) / (exp(b) - 1.0)

            # includes missing displacement to allow T to reach Tmin, this
            # removes a discontinuity in the original Parton and Logan eqn.
            # See Kimball and Bellamy (1986) Energy in Agriculture, 5, 185-197
            tday[i-1] = (tmin -d) + (tset - tmin - d) * \
                        exp(-b * n / (night_length + c))


    return (tday)

def calculate_solar_geometry(doy, latitude, longitude):

    """
    The solar zenith angle is the angle between the zenith and the centre
    of the sun's disc. The solar elevation angle is the altitude of the
    sun, the angle between the horizon and the centre of the sun's disc.
    Since these two angles are complementary, the cosine of either one of
    them equals the sine of the other, i.e. cos theta = sin beta. I will
    use cos_zen throughout code for simplicity.
    Arguments:
    ----------
    params : p
        params structure
    doy : double
        day of year
    hod : double:
        hour of the day [0.5 to 24]
    cos_zen : double
        cosine of the zenith angle of the sun in degrees (returned)
    elevation : double
        solar elevation (degrees) (returned)
    References:
    -----------
    * De Pury & Farquhar (1997) PCE, 20, 537-557.
    """

    elevation = np.zeros(48)
    cos_zenith = np.zeros(48)
    for i in xrange(1, 48+1):
        # need to convert 30 min data, 0-47 to 0-23.5
        hod = i / 2.0

        gamma = day_angle(doy)
        dec = calculate_solar_declination(doy, gamma)
        et = calculate_eqn_of_time(gamma)
        t0 = calculate_solar_noon(et, longitude)
        h = calculate_hour_angle(hod, t0)
        rlat = latitude * pi / 180.0

        # A13 - De Pury & Farquhar
        sin_beta = sin(rlat) * sin(dec) + cos(rlat) * cos(dec) * cos(h)
        cos_zenith[i-1] = sin_beta; # The same thing, going to use throughout
        if cos_zenith[i-1] > 1.0:
            cos_zenith[i-1] = 1.0
        elif cos_zenith[i-1] < 0.0:
            cos_zenith[i-1] = 0.0

        zenith_angle = 180.0 / pi * (acos(cos_zenith[i-1]))
        elevation[i-1] = 90.0 - zenith_angle

    return (elevation, cos_zenith)


def calculate_solar_noon(et, longitude):
    """
    Calculation solar noon - De Pury & Farquhar, '97: eqn A16
    Reference:
    ----------
    * De Pury & Farquhar (1997) PCE, 20, 537-557.
    Returns:
    ---------
    t0 - solar noon (hours).
    """
    # all international standard meridians are multiples of 15deg east/west of
    # greenwich
    Ls = round_to_value(longitude, 15.)
    t0 = 12.0 + (4.0 * (Ls - longitude) - et) / 60.0

    return (t0)

def round_to_value(number, roundto):
    return round(number / roundto) * roundto



def calculate_solar_declination(doy, gamma):
    """
    Solar Declination Angle is a function of day of year and is indepenent
    of location, varying between 23deg45' to -23deg45'
    Arguments:
    ----------
    doy : int
        day of year, 1=jan 1
    gamma : double
        fractional year (radians)
    Returns:
    --------
    dec: float
        Solar Declination Angle [radians]
    Reference:
    ----------
    * De Pury & Farquhar (1997) PCE, 20, 537-557.
    * Leuning et al (1995) Plant, Cell and Environment, 18, 1183-1200.
    * J. W. Spencer (1971). Fourier series representation of the position of
      the sun.
    """

    # declination (radians) */
    #decl = 0.006918 - 0.399912 * cos(gamma) + 0.070257 * sin(gamma) - \
    #       0.006758 * cos(2.0 * gamma) + 0.000907 * sin(2.0 * gamma) -\
    #       0.002697 * cos(3.0 * gamma) + 0.00148 * sin(3.0 * gamma);*/

    # (radians) A14 - De Pury & Farquhar
    decl = -23.4 * (pi / 180.) * cos(2.0 * pi * (doy + 10) / 365)

    return (decl)

def calculate_hour_angle(t, t0):
    """
    Calculation solar noon - De Pury & Farquhar, '97: eqn A15
    Reference:
    ----------
    * De Pury & Farquhar (1997) PCE, 20, 537-557.
    Returns:
    ---------
    h - hour angle (radians).
    """
    return (pi * (t - t0) / 12.0)


def day_angle(doy):
    """
    Calculation of day angle - De Pury & Farquhar, '97: eqn A18
    Reference:
    ----------
    * De Pury & Farquhar (1997) PCE, 20, 537-557.
    * J. W. Spencer (1971). Fourier series representation of the position of
      the sun.
    Returns:
    ---------
    gamma - day angle in radians.
    """

    return (2.0 * pi * (doy - 1.0) / 365.0)

def calculate_eqn_of_time(gamma):
    """
    Equation of time - correction for the difference btw solar time
    and the clock time.
    Arguments:
    ----------
    doy : int
        day of year
    gamma : double
        fractional year (radians)
    References:
    -----------
    * De Pury & Farquhar (1997) PCE, 20, 537-557.
    * Campbell, G. S. and Norman, J. M. (1998) Introduction to environmental
      biophysics. Pg 169.
    * J. W. Spencer (1971). Fourier series representation of the position of
      the sun.
    * Hughes, David W.; Yallop, B. D.; Hohenkerk, C. Y. (1989),
      "The Equation of Time", Monthly Notices of the Royal Astronomical
      Society 238: 1529-1535
    """

    # minutes - de Pury and Farquhar, 1997 - A17
    et = (0.017 + 0.4281 * cos(gamma) - 7.351 * sin(gamma) - 3.349 *
          cos(2.0 * gamma) - 9.731  * sin(gamma))

    return (et)

def calc_extra_terrestrial_irradiance(doy, cos_zenith):
    """
    Solar radiation incident outside the earth's atmosphere, e.g.
    extra-terrestrial radiation. The value varies a little with the earths
    orbit.
    Using formula from Spitters not Leuning!
    Arguments:
    ----------
    doy : double
        day of year
    cos_zenith : double
        cosine of zenith angle (radians)
    Returns:
    --------
    So : float
        solar radiation normal to the sun's bean outside the Earth's atmosphere
        (W m-2)
    Reference:
    ----------
    * Spitters et al. (1986) AFM, 38, 217-229, equation 1.
    """
    Sc = 1370.0 # W m-2

    # remember sin_beta = cos_zenith; trig funcs are cofuncs of each other
    # sin(x) = cos(90-x) and cos(x) = sin(90-x).
    So = Sc * (1.0 + 0.033 * cos(doy / 365.0 * 2.0 * pi)) * cos_zenith;

    return (So)

def estimate_clearness(sw_rad, So):
    """
    estimate atmospheric transmisivity - the amount of diffuse radiation
    is a function of the amount of haze and/or clouds in the sky. Estimate
    a proxy for this, i.e. the ratio between global solar radiation on a
    horizontal surface at the ground and the extraterrestrial solar
    radiation
    """

    # catch possible divide by zero when zenith = 90.
    if So <= 0.0:
        tau = 0.0
    else:
        tau = sw_rad / So

    if tau > 1.0:
        tau = 1.0;
    elif tau < 0.0:
        tau = 0.0

    return (tau)


def spitters(doy, sw_rad, cos_zenith):
    """
    Spitters algorithm to estimate the diffuse component from the measured
    irradiance.
    Parameters:
    ----------
    doy : int
        day of year
    par : double
        total par measured [umol m-2 s-1]
    Returns:
    -------
    diffuse : double
        diffuse component of incoming radiation
    References:
    ----------
    * Spitters, C. J. T., Toussaint, H. A. J. M. and Goudriaan, J. (1986)
      Separating the diffuse and direct component of global radiation and its
      implications for modeling canopy photosynthesis. Part I. Components of
      incoming radiation. Agricultural Forest Meteorol., 38:217-229.
    """

    diffuse_frac = np.zeros(48)
    direct_frac = np.zeros(48)
    for i in xrange(1, 48+1):
        # need to convert 30 min data, 0-47 to 0-23.5
        hod = i / 2.0

        So = calc_extra_terrestrial_irradiance(doy, cos_zenith[i-1]);

        # atmospheric transmisivity #
        tau = estimate_clearness(sw_rad, So)

        # For zenith angles > 80 degrees, diffuse_frac = 1.0
        if cos_zenith[i-1] > 0.17:
            # the ratio between diffuse and total Solar irradiance (R), eqn 20
            R = 0.847 - 1.61 * cos_zenith[i-1] + 1.04 * cos_zenith[i-1]**2
            K = (1.47 - R) / 1.66
            if tau <= 0.22:
                diffuse_frac[i-1] = 1.0;
            elif tau > 0.22 and tau <= 0.35:
                diffuse_frac[i-1] = 1.0 - 6.4 * (tau - 0.22)**2
            elif tau > 0.35 and tau <= K:
                diffuse_frac[i-1] = 1.47 - 1.66 * tau
            else:
                diffuse_frac[i-1] = R
        else:
            diffuse_frac[i-1] = 1.0

        if diffuse_frac[i-1] <= 0.0:
            diffuse_frac[i-1] = 0.0
        elif diffuse_frac[i-1] >= 1.0:
            diffuse_frac[i-1]= 1.0

        direct_frac[i-1] = 1.0 - diffuse_frac[i-1]

    return (direct_frac, diffuse_frac)

if __name__ == "__main__":

    main()
