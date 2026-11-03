# Reference values for the OpenPrism validation suite, computed with R.
#
#   Rscript validation/reference.R      (writes validation/reference_r.json)
#
# Requires R >= 4.0 with: jsonlite survival MASS metafor psych car lmtest quantreg circular nlme coin
# Datasets are R's classic built-in examples (or simulated with a fixed seed),
# exported together with the results so that the Python side analyses exactly
# the same numbers. Every value is computed by an established R function,
# independent of OpenPrism's (Python) implementation.
suppressMessages({
  library(jsonlite); library(survival); library(MASS); library(metafor); library(psych)
  library(car); library(lmtest); library(quantreg); library(circular); library(nlme); library(coin)
})
D <- list(); R <- list()
n <- function(x) unname(as.numeric(x))
ci <- function(h) n(h$conf.int)

# ------------------------------------------------------------------ t tests & friends (sleep)
g1 <- sleep$extra[sleep$group == 1]; g2 <- sleep$extra[sleep$group == 2]
D$sleep <- list(g1 = g1, g2 = g2)
h <- t.test(g2, g1, var.equal = TRUE); R$t_student <- list(t = n(h$statistic), df = n(h$parameter), p = h$p.value, ci = ci(h))
h <- t.test(g2, g1); R$t_welch <- list(t = n(h$statistic), df = n(h$parameter), p = h$p.value, ci = ci(h))
h <- t.test(g2, g1, paired = TRUE); R$t_paired <- list(t = n(h$statistic), df = n(h$parameter), p = h$p.value, ci = ci(h))
h <- t.test(g2 - g1, mu = 0); R$t_one <- list(t = n(h$statistic), p = h$p.value, ci = ci(h))
h <- suppressWarnings(wilcox.test(g2, g1, exact = FALSE, correct = TRUE)); R$mw <- list(W = n(h$statistic), p = h$p.value)
h <- suppressWarnings(wilcox.test(g2, g1, paired = TRUE, exact = FALSE, correct = TRUE)); R$wsr <- list(V = n(h$statistic), p = h$p.value)
R$mw_exact <- as.numeric(pvalue(wilcox_test(extra ~ group, data = sleep, distribution = "exact")))
R$wsr_exact <- as.numeric(pvalue(wilcoxsign_test(g2 ~ g1, distribution = "exact", zero.method = "Wilcoxon")))
R$shapiro <- list(W1 = n(shapiro.test(g1)$statistic), p1 = shapiro.test(g1)$p.value, W2 = n(shapiro.test(g2)$statistic), p2 = shapiro.test(g2)$p.value)
h <- var.test(g2, g1); R$ftest <- list(F = n(h$statistic), p = h$p.value, ci = ci(h))
R$desc <- list(mean = mean(g2), sd = sd(g2), q = n(quantile(g2, c(.25, .5, .75), type = 6)),
               ci = n(t.test(g2)$conf.int))

# continuous samples without ties (fixed seed) for distribution / scale tests
set.seed(11); x <- round(rnorm(14, 10, 2), 4); y <- round(rnorm(17, 11, 3.5), 4); z <- round(rnorm(12, 10.5, 1.2), 4)
D$cont <- list(x = x, y = y, z = z)
h <- ks.test(x, y); R$ks <- list(D = n(h$statistic), p = h$p.value)
h <- ansari.test(x, y); R$ansari <- list(AB = n(h$statistic), p = h$p.value)
h <- mood.test(x, y); R$mood <- list(Z = n(h$statistic), p = h$p.value)
h <- fligner.test(list(x, y, z)); R$fligner <- list(stat = n(h$statistic), p = h$p.value)
h <- bartlett.test(list(x, y, z)); R$bartlett <- list(stat = n(h$statistic), p = h$p.value)
grp <- factor(rep(c("x", "y", "z"), c(length(x), length(y), length(z)))); vv <- c(x, y, z)
h <- leveneTest(vv, grp, center = median); R$bf <- list(F = h$`F value`[1], p = h$`Pr(>F)`[1])
h <- leveneTest(vv, grp, center = mean); R$levene <- list(F = h$`F value`[1], p = h$`Pr(>F)`[1])
# effect sizes: Cohen's d with noncentral-t CI by uniroot (independent implementation)
sp <- sqrt(((length(x) - 1) * var(x) + (length(y) - 1) * var(y)) / (length(x) + length(y) - 2))
d <- (mean(y) - mean(x)) / sp; tt <- d / sqrt(1 / length(x) + 1 / length(y)); dfd <- length(x) + length(y) - 2
lo <- suppressWarnings(uniroot(function(nc) pt(tt, dfd, nc) - 0.975, c(-20, 20), tol = 1e-12))$root
hi <- suppressWarnings(uniroot(function(nc) pt(tt, dfd, nc) - 0.025, c(-20, 20), tol = 1e-12))$root
J <- exp(lgamma(dfd / 2) - log(sqrt(dfd / 2)) - lgamma((dfd - 1) / 2))
cliff <- mean(sign(outer(y, x, "-")))
R$effect <- list(d = d, lo = lo * sqrt(1 / length(x) + 1 / length(y)), hi = hi * sqrt(1 / length(x) + 1 / length(y)), g = d * J, cliff = cliff,
                 glass = (mean(y) - mean(x)) / sd(x))

# ------------------------------------------------------------------ one-way ANOVA (PlantGrowth)
pg <- split(PlantGrowth$weight, PlantGrowth$group); D$plant <- lapply(pg, n)
a <- summary(aov(weight ~ group, PlantGrowth))[[1]]
tk <- TukeyHSD(aov(weight ~ group, PlantGrowth))$group
R$anova <- list(F = a$`F value`[1], p = a$`Pr(>F)`[1], ssb = a$`Sum Sq`[1], ssw = a$`Sum Sq`[2],
                tukey_diff = n(tk[, "diff"]), tukey_lwr = n(tk[, "lwr"]), tukey_upr = n(tk[, "upr"]), tukey_p = n(tk[, "p adj"]),
                tukey_names = rownames(tk))
h <- kruskal.test(weight ~ group, PlantGrowth); R$kw <- list(H = n(h$statistic), p = h$p.value)
h <- oneway.test(weight ~ group, PlantGrowth); R$welch_anova <- list(F = n(h$statistic), df2 = n(h$parameter[2]), p = h$p.value)

# ------------------------------------------------------------------ repeated measures, nonparametric
RoundingTimes <- matrix(c(5.40, 5.50, 5.55, 5.85, 5.70, 5.75, 5.20, 5.60, 5.50, 5.55, 5.50, 5.40, 5.90, 5.85, 5.70, 5.45, 5.55, 5.60,
  5.40, 5.40, 5.35, 5.45, 5.50, 5.35, 5.25, 5.15, 5.00, 5.85, 5.80, 5.70, 5.25, 5.20, 5.10, 5.65, 5.55, 5.45, 5.60, 5.35, 5.45,
  5.05, 5.00, 4.95, 5.50, 5.50, 5.40, 5.45, 5.55, 5.50, 5.55, 5.55, 5.35, 5.45, 5.50, 5.55, 5.50, 5.45, 5.25, 5.65, 5.60, 5.40,
  5.70, 5.65, 5.55, 6.30, 6.30, 6.25), nrow = 22, byrow = TRUE)
D$rounding <- lapply(1:3, function(j) RoundingTimes[, j])
h <- friedman.test(RoundingTimes); R$friedman <- list(chi = n(h$statistic), p = h$p.value)
h <- quade.test(RoundingTimes); R$quade <- list(F = n(h$statistic), p = h$p.value)

# ------------------------------------------------------------------ regression & correlation (cars)
D$cars <- list(speed = cars$speed, dist = cars$dist)
m <- lm(dist ~ speed, cars); s <- summary(m)
R$lm <- list(b = n(coef(m)), se = n(s$coefficients[, 2]), r2 = s$r.squared, sigma = s$sigma, F = n(s$fstatistic[1]))
h <- cor.test(cars$speed, cars$dist); R$pearson <- list(r = n(h$estimate), p = h$p.value, ci = ci(h))
h <- suppressWarnings(cor.test(cars$speed, cars$dist, method = "spearman", exact = FALSE)); R$spearman <- list(r = n(h$estimate), p = h$p.value)
h <- suppressWarnings(cor.test(cars$speed, cars$dist, method = "kendall", exact = FALSE)); R$kendall <- list(r = n(h$estimate), p = h$p.value)
R$bp <- list(stat = n(bptest(m)$statistic), p = bptest(m)$p.value)
R$dw <- n(dwtest(m)$statistic)
h <- resettest(m, power = 2:3, type = "fitted"); R$reset <- list(F = n(h$statistic), p = h$p.value)
h <- bgtest(m, order = 1); R$bg <- list(stat = n(h$statistic), p = h$p.value)
R$huber <- n(coef(rlm(dist ~ speed, cars, psi = psi.huber, k = 1.345, scale.est = "MAD", maxit = 200, acc = 1e-12)))
R$lad <- n(coef(rq(dist ~ speed, tau = 0.5, data = cars)))
sl <- outer(cars$dist, cars$dist, "-") / outer(cars$speed, cars$speed, "-"); sl <- sl[upper.tri(sl)]; sl <- sl[is.finite(sl)]
R$theilsen <- median(sl)

# multiple regression / GLMs (mtcars)
D$mtcars <- lapply(mtcars[, c("mpg", "wt", "hp", "qsec", "am", "gear")], n)
m <- lm(mpg ~ wt + hp + qsec, mtcars); s <- summary(m)
R$mlr <- list(b = n(coef(m)), se = n(s$coefficients[, 2]), r2 = s$r.squared, adj = s$adj.r.squared, sigma = s$sigma, F = n(s$fstatistic[1]))
m <- glm(am ~ wt + hp, binomial, mtcars); R$logit <- list(b = n(coef(m)), se = n(summary(m)$coefficients[, 2]), dev = deviance(m), aic = AIC(m))
m <- glm(am ~ wt + hp, binomial(link = "probit"), mtcars); R$probit <- list(b = n(coef(m)), se = n(summary(m)$coefficients[, 2]), dev = deviance(m))
m <- glm(mpg ~ wt + hp, Gamma(link = "log"), mtcars); R$gamma <- list(b = n(coef(m)), se = n(summary(m)$coefficients[, 2]), dev = deviance(m))
m <- polr(factor(gear) ~ wt + hp, mtcars, Hess = TRUE); R$polr <- list(b = n(coef(m)), se = n(sqrt(diag(vcov(m)))[1:2]), zeta = n(m$zeta))
# partial correlation by the residual method
pc <- function(a, b, c) cor(resid(lm(a ~ c)), resid(lm(b ~ c)))
R$pcor <- list(mpg_wt = pc(mtcars$mpg, mtcars$wt, mtcars$hp), mpg_hp = pc(mtcars$mpg, mtcars$hp, mtcars$wt), wt_hp = pc(mtcars$wt, mtcars$hp, mtcars$mpg))

# Poisson (warpbreaks, dummy-coded) and negative binomial (quine)
wb <- warpbreaks
D$warp <- list(breaks = wb$breaks, woolB = as.numeric(wb$wool == "B"), tensionM = as.numeric(wb$tension == "M"), tensionH = as.numeric(wb$tension == "H"))
m <- glm(breaks ~ wool + tension, poisson, wb); R$poisson <- list(b = n(coef(m)), se = n(summary(m)$coefficients[, 2]), dev = deviance(m), aic = AIC(m))
D$quine <- list(Days = quine$Days, EthN = as.numeric(quine$Eth == "N"), SexM = as.numeric(quine$Sex == "M"))
m <- glm.nb(Days ~ Eth + Sex, quine); R$negbin <- list(b = n(coef(m)), se = n(summary(m)$coefficients[, 2]), theta = m$theta)

# nonlinear regression (Puromycin, treated)
pt_ <- Puromycin[Puromycin$state == "treated", ]
D$puromycin <- list(conc = pt_$conc, rate = pt_$rate)
m <- nls(rate ~ Vm * conc / (K + conc), pt_, start = list(Vm = 200, K = 0.1)); s <- summary(m)
R$nls <- list(b = n(coef(m)), se = n(s$coefficients[, 2]), sigma = s$sigma)

# two-way ANOVA (ToothGrowth, balanced)
D$tooth <- list(len = ToothGrowth$len, supp = as.character(ToothGrowth$supp), dose = ToothGrowth$dose)
a <- summary(aov(len ~ supp * factor(dose), ToothGrowth))[[1]]
R$twoway <- list(F = n(a$`F value`[1:3]), p = n(a$`Pr(>F)`[1:3]))

# ------------------------------------------------------------------ counts
tea <- matrix(c(3, 1, 1, 3), 2); h <- fisher.test(tea); R$fisher <- list(p = h$p.value, or = n(h$estimate), ci = ci(h))
perf <- matrix(c(794, 86, 150, 570), 2); D$performance <- perf
R$mcnemar <- list(chi = n(mcnemar.test(perf)$statistic), p = mcnemar.test(perf)$p.value,
                  chi_nc = n(mcnemar.test(perf, correct = FALSE)$statistic), p_nc = mcnemar.test(perf, correct = FALSE)$p.value)
M3 <- matrix(c(25, 6, 3, 8, 30, 5, 2, 9, 28), 3, byrow = TRUE); D$square3 <- M3
h <- mcnemar.test(M3); R$bowker <- list(chi = n(h$statistic), df = n(h$parameter), p = h$p.value)
rc <- matrix(c(32, 12, 9, 14, 22, 18, 7, 11, 29), 3, byrow = TRUE); D$rc <- rc
h <- chisq.test(rc, correct = FALSE); R$chisq <- list(chi = n(h$statistic), p = h$p.value)
smokers <- c(83, 90, 129, 70); patients <- c(86, 93, 136, 82); D$smokers <- list(smokers = smokers, patients = patients)
h <- prop.trend.test(smokers, patients); R$trend <- list(chi = n(h$statistic), p = h$p.value)
h <- binom.test(682, 925, p = 0.75); R$binom <- list(p = h$p.value, ci = ci(h))
R$wilson <- n(prop.test(682, 925, correct = FALSE)$conf.int)
R$jeffreys <- qbeta(c(0.025, 0.975), 682 + 0.5, 925 - 682 + 0.5)
ucb <- lapply(1:6, function(d) matrix(as.numeric(t(UCBAdmissions[, , d])), 2)); D$ucb <- ucb
h <- mantelhaen.test(UCBAdmissions, correct = FALSE); R$cmh <- list(chi = n(h$statistic), p = h$p.value, or = n(h$estimate), ci = ci(h))
kap <- matrix(c(44, 5, 1, 7, 20, 3, 2, 4, 14), 3, byrow = TRUE); D$kappa <- kap
ck <- cohen.kappa(kap, alpha = 0.05)
R$kappa <- list(kappa = ck$kappa, weighted = ck$weighted.kappa)
# risk measures (independent formulas)
a <- 15; b <- 85; c <- 30; d <- 70; D$risk <- matrix(c(a, b, c, d), 2, byrow = TRUE)
R$risk <- list(rr = (a / (a + b)) / (c / (c + d)), rr_ci = exp(log((a / (a + b)) / (c / (c + d))) + c(-1, 1) * qnorm(0.975) * sqrt(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d))),
               or = a * d / (b * c), or_cond = n(fisher.test(D$risk)$estimate), or_cond_ci = ci(fisher.test(D$risk)))

# ------------------------------------------------------------------ survival (aml)
D$aml <- list(time = aml$time, status = aml$status, maintained = as.numeric(aml$x == "Maintained"))
R$logrank <- list(chi = survdiff(Surv(time, status) ~ x, aml)$chisq, chi_peto = survdiff(Surv(time, status) ~ x, aml, rho = 1)$chisq)
m <- coxph(Surv(time, status) ~ I(as.numeric(x == "Maintained")), aml)  # Efron ties (R default)
R$cox <- list(b = n(coef(m)), se = n(sqrt(diag(vcov(m)))), p = summary(m)$coefficients[1, 5])
fit <- survfit(Surv(time, status) ~ x, aml)
tab <- summary(fit, rmean = 40)$table
R$rmst <- list(rmean = n(tab[, "rmean"]), se = n(tab[, "se(rmean)"]), median = n(tab[, "median"]))

# ------------------------------------------------------------------ reliability, meta-analysis, circular, multivariate
sf <- matrix(c(9, 2, 5, 8, 6, 1, 3, 2, 8, 4, 6, 8, 7, 1, 2, 6, 10, 5, 6, 9, 6, 2, 4, 7), ncol = 4, byrow = TRUE); D$sf <- sf
ic <- ICC(sf, lmer = FALSE)$results
R$icc <- list(icc = n(ic$ICC), lo = n(ic$`lower bound`), hi = n(ic$`upper bound`), type = as.character(ic$type))
R$alpha <- suppressWarnings(psych::alpha(sf, warnings = FALSE)$total$raw_alpha)

bcg <- dat.bcg; D$bcg <- list(e1 = bcg$tpos, n1 = bcg$tpos + bcg$tneg, e2 = bcg$cpos, n2 = bcg$cpos + bcg$cneg, study = paste(bcg$author, bcg$year))
es <- escalc(measure = "RR", ai = tpos, bi = tneg, ci = cpos, di = cneg, data = bcg)
meta <- function(m) list(b = n(m$b), se = m$se, lo = m$ci.lb, hi = m$ci.ub, tau2 = m$tau2, I2 = m$I2, Q = m$QE, p = m$pval)
R$meta_reml <- meta(rma(yi, vi, data = es, method = "REML"))
R$meta_dl <- meta(rma(yi, vi, data = es, method = "DL"))
R$meta_pm <- meta(rma(yi, vi, data = es, method = "PM"))
R$meta_fe <- meta(rma(yi, vi, data = es, method = "FE"))
R$meta_hk <- meta(rma(yi, vi, data = es, method = "REML", test = "knha"))
eg <- regtest(rma(yi, vi, data = es, method = "FE"), model = "lm", predictor = "sei"); R$egger <- list(t = n(eg$zval), p = eg$pval)
pr <- predict(rma(yi, vi, data = es, method = "REML")); R$meta_pi <- c(pr$pi.lb, pr$pi.ub)

set.seed(3); ang1 <- round((as.numeric(rvonmises(25, circular(pi / 3), 2)) * 180 / pi) %% 360, 3)
ang2 <- round((as.numeric(rvonmises(20, circular(pi / 2), 2)) * 180 / pi) %% 360, 3); D$angles <- list(a = ang1, b = ang2)
ca <- circular(ang1, units = "degrees", template = "none")
rt <- rayleigh.test(ca)
R$circ <- list(mean = (as.numeric(mean(ca)) %% 360), rbar = as.numeric(rho.circular(ca)), rayleigh_p = rt$p.value)
ww <- watson.williams.test(list(circular(ang1, units = "degrees"), circular(ang2, units = "degrees")))
R$ww <- list(F = n(ww$statistic), p = ww$p.value)
# Zar (2010) variant: kappa from the within-sample mean resultant length (exact ML inversion)
rr <- c(rho.circular(circular(ang1, units = "degrees")), rho.circular(circular(ang2, units = "degrees"))); ns <- c(length(ang1), length(ang2)); N <- sum(ns)
Rall <- rho.circular(circular(c(ang1, ang2), units = "degrees")) * N
kw <- uniroot(function(k) besselI(k, 1, expon.scaled = TRUE) / besselI(k, 0, expon.scaled = TRUE) - sum(rr * ns) / N, c(1e-8, 1e4), tol = 1e-15)$root  # exact ML kappa
R$ww_zar <- (1 + 3 / (8 * kw)) * ((N - 2) * (sum(rr * ns) - Rall)) / ((2 - 1) * (N - sum(rr * ns)))

D$iris <- lapply(iris[, 1:4], n); D$species <- as.numeric(iris$Species)
mv <- manova(cbind(Sepal.Length, Petal.Length, Sepal.Width) ~ Species, iris)
sp_ <- summary(mv, test = "Pillai")$stats; sw <- summary(mv, test = "Wilks")$stats
R$manova <- list(pillai = sp_[1, 2], pillai_F = sp_[1, 3], wilks = sw[1, 2], wilks_F = sw[1, 3])
hc <- cutree(hclust(dist(scale(iris[, 1:4])), method = "ward.D2"), k = 3); R$ward_sizes <- sort(n(table(hc)))

# ------------------------------------------------------------------ time series & trends (Nile)
D$nile <- n(Nile)
h <- Box.test(Nile, lag = 10, type = "Ljung-Box"); R$ljung <- list(Q = n(h$statistic), p = h$p.value)
h <- suppressWarnings(cor.test(seq_along(Nile), as.numeric(Nile), method = "kendall", exact = FALSE, continuity = TRUE))
R$mk <- list(tau = n(h$estimate), p = h$p.value)

# ------------------------------------------------------------------ cosinor (simulated, fixed seed)
set.seed(7); tt <- seq(0, 46, by = 2); yy <- round(10 + 3 * cos(2 * pi * (tt - 8) / 24) + rnorm(length(tt), 0, 0.6), 4)
D$cos <- list(t = tt, y = yy)
m <- lm(yy ~ cos(2 * pi * tt / 24) + sin(2 * pi * tt / 24)); b <- coef(m)
R$cosinor <- list(mesor = n(b[1]), amp = sqrt(b[2]^2 + b[3]^2), F = n(summary(m)$fstatistic[1]),
                  peak = ((atan2(b[3], b[2]) %% (2 * pi)) * 24 / (2 * pi)))

# ------------------------------------------------------------------ mixed model (Orthodont: subject × age)
o <- Orthodont; D$ortho <- lapply(split(o$distance, o$age), n)
m <- lme(distance ~ factor(age), random = ~ 1 | Subject, data = o, method = "REML")
R$lme <- list(sigma = m$sigma, sd_subject = as.numeric(VarCorr(m)[1, 2]), fixed = n(fixef(m)))

# random intercept + random slope (Orthodont: distance ~ age + Sex, random = ~ age | Subject)
D$ortho_long <- list(distance = o$distance, age = o$age, subject = as.numeric(o$Subject), male = as.numeric(o$Sex == "Male"))
m <- lme(distance ~ age + I(as.numeric(Sex == "Male")), random = ~ age | Subject, data = o, method = "REML", control = lmeControl(opt = "optim", maxIter = 200, msMaxIter = 200))
vc <- VarCorr(m)
R$lme_slope <- list(fixed = n(fixef(m)), se = n(sqrt(diag(vcov(m)))), sd_int = as.numeric(vc[1, 2]), sd_slope = as.numeric(vc[2, 2]),
                    corr = as.numeric(vc[2, 3]), sigma = m$sigma, loglik = as.numeric(logLik(m)))

# ------------------------------------------------------------------ extended references (lmerTest, DescTools, WRS2, ARTool, clinfun, epiR, coin)
suppressMessages({library(lmerTest); library(DescTools); library(WRS2); library(ARTool); library(clinfun); library(epiR)})
o2 <- Orthodont; o2$male <- as.numeric(o2$Sex == "Male")
m <- lmer(distance ~ age + male + (age | Subject), data = o2, REML = TRUE)
cs <- summary(m, ddf = "Satterthwaite")$coefficients
R$lmert <- list(est = n(cs[, 1]), se = n(cs[, 2]), df = n(cs[, 3]), p = n(cs[, 5]))
m2 <- lmer(distance ~ factor(age) + male + (1 | Subject), data = o2, REML = TRUE)
a2 <- anova(m2, ddf = "Satterthwaite")
R$lmert_f <- list(F = n(a2[, "F value"]), dendf = n(a2[, "DenDF"]), p = n(a2[, "Pr(>F)"]))
pgw <- PlantGrowth
dn <- DunnTest(weight ~ group, data = pgw, method = "none")[[1]]
R$dunn <- list(names = rownames(dn), p = n(dn[, "pval"]))
cn <- ConoverTest(weight ~ group, data = pgw, method = "none")[[1]]
R$conover <- list(names = rownames(cn), p = n(cn[, "pval"]))
# DescTools' normal approximation has no tie correction: compare on tie-free data
jt <- JonckheereTerpstraTest(list(x, y, z), exact = FALSE)
R$jt <- list(stat = n(jt$statistic), p = jt$p.value)
yu <- yuen(v ~ g, data = data.frame(v = c(x, y), g = factor(rep(c("x", "y"), c(length(x), length(y))))), tr = 0.2)
R$yuen <- list(t = yu$test, df = yu$df, p = yu$p.value, diff = yu$diff, ci = n(yu$conf.int))
t1 <- t1way(weight ~ group, data = pgw, tr = 0.2)
R$t1way <- list(F = t1$test, df1 = t1$df1, df2 = t1$df2, p = t1$p.value)
suppressMessages(library(PMCMRplus))
ds <- dscfAllPairsTest(weight ~ group, data = pgw); R$dscf <- list(p = n(ds$p.value[lower.tri(ds$p.value, diag = TRUE)]), names = "trt1-ctrl,trt2-ctrl,trt2-trt1")
rtm <- RoundingTimes; colnames(rtm) <- c("A", "B", "C"); rownames(rtm) <- paste0("s", seq_len(nrow(rtm))); nm <- frdAllPairsNemenyiTest(rtm); R$nemenyi <- n(nm$p.value[lower.tri(nm$p.value, diag = TRUE)])
tg <- ToothGrowth; tg$dose <- factor(tg$dose)
am <- anova(art(len ~ supp * dose, data = tg))
R$art <- list(F = n(am$F), terms = as.character(am$Term))
ck <- CohenKappa(kap, conf.level = 0.95); ckq <- CohenKappa(kap, weights = "Fleiss-Cohen", conf.level = 0.95); ckl <- CohenKappa(kap, weights = "Equal-Spacing", conf.level = 0.95)
R$kappa_ci <- list(k = n(ck), kq = n(ckq), kl = n(ckl))
cc <- CCC(g1, g2)$rho.c; R$ccc <- n(cc[1, ])
R$kendallw <- KendallW(sf, correct = TRUE)
R$assoc <- list(gamma = GoodmanKruskalGamma(rc), taub = KendallTauB(rc), somers_r = SomersDelta(rc, direction = "row"), somers_c = SomersDelta(rc, direction = "column"))
gt <- GTest(rc, correct = "none"); gtw <- GTest(rc, correct = "williams")
R$gtest <- list(G = n(gt$statistic), p = gt$p.value, Gw = n(gtw$statistic))
sm <- StuartMaxwellTest(M3); R$stuart <- list(stat = n(sm$statistic), p = sm$p.value)
ucb_arr <- UCBAdmissions
bd <- BreslowDayTest(ucb_arr, correct = TRUE); R$breslowday <- list(stat = n(bd$statistic), p = bd$p.value)
R$jb <- list(stat = n(JarqueBeraTest(g2, robust = FALSE)$statistic), p = JarqueBeraTest(g2, robust = FALSE)$p.value)
sfx <- c(x, y); R$sf <- list(W = n(ShapiroFranciaTest(sfx)$statistic), p = ShapiroFranciaTest(sfx)$p.value)
rt <- RunsTest(as.numeric(Nile), exact = FALSE, correct = FALSE); R$runs <- list(z = n(rt$statistic), p = rt$p.value)
vn <- VonNeumannTest(as.numeric(Nile), unbiased = FALSE); R$vonneumann <- list(stat = n(vn$statistic), p = vn$p.value)
R$sdci <- sqrt(n(VarCI(g2, method = "classic"))[2:3])
R$signtest <- SignTest(g2, mu = 1)$p.value
R$agresti <- n(BinomCI(682, 925, method = "agresti-coull")[1, 2:3])
dg <- epi.tests(as.table(matrix(c(90, 10, 15, 185), 2, dimnames = list(c("Dis+", "Dis-"), c("Test+", "Test-")))), conf.level = 0.95)
dd <- dg$detail
R$diag <- list(se = n(dd[dd$statistic == "se", 2:4]), sp = n(dd[dd$statistic == "sp", 2:4]), lrpos = n(dd[dd$statistic == "lr.pos", 2:4]), lrneg = n(dd[dd$statistic == "lr.neg", 2:4]))
# weighted log-rank tests with the hypergeometric variance (independent R implementation of
# Klein & Moeschberger section 7.3; coin uses a permutation variance instead)
wlr <- function(time, status, grp, wfun) {
  ut <- sort(unique(time[status == 1])); U <- 0; V <- 0; Sp <- 1
  for (t in ut) {
    n1 <- sum(time >= t & grp == 1); n <- sum(time >= t); d1 <- sum(time == t & status == 1 & grp == 1); d <- sum(time == t & status == 1)
    Sp <- Sp * (1 - d / (n + 1))
    w <- wfun(n, Sp)
    U <- U + w * (d1 - d * n1 / n)
    if (n > 1) V <- V + w^2 * d * (n1 / n) * (1 - n1 / n) * (n - d) / (n - 1)
  }
  U^2 / V
}
gr <- as.numeric(aml$x == "Maintained")
R$weighted_lr <- list(tw = wlr(aml$time, aml$status, gr, function(n, s) sqrt(n)), pp = wlr(aml$time, aml$status, gr, function(n, s) s),
                      gehan = wlr(aml$time, aml$status, gr, function(n, s) n))

# competing risks (simulated, fixed seed): cumulative incidence by cmprsk::cuminc
suppressMessages(library(cmprsk))
set.seed(5); nn <- 60; tt1 <- rexp(nn, 0.08); tt2 <- rexp(nn, 0.05); cc <- runif(nn, 5, 30)
ftime <- round(pmin(tt1, tt2, cc), 3); fstat <- ifelse(ftime == round(cc, 3), 0, ifelse(tt1 < tt2, 1, 2))
D$cr <- list(time = ftime, status = fstat)
ci <- cuminc(ftime, fstat, cencode = 0)
tp <- c(2, 5, 10, 20)
R$cuminc <- list(times = tp, est = n(timepoints(ci, tp)$est[1, ]))
# Gray's test and Fine-Gray regression (independent simulated data with a group effect and ties)
set.seed(21); nn <- 150; grp <- rep(0:2, length.out = nn); xc <- round(rnorm(nn), 2)
u1 <- rexp(nn, 0.06 * exp(0.6 * (grp == 1) + 0.3 * xc)); u2 <- rexp(nn, 0.05); uc <- runif(nn, 3, 35)
gt <- round(pmin(u1, u2, uc), 1); gs <- ifelse(pmin(u1, u2) > uc, 0, ifelse(u1 < u2, 1, 2))
D$gray <- list(time = gt, status = gs, group = grp, x = xc)
gtie <- cuminc(gt, gs, group = grp); gnt <- cuminc(pmin(u1, u2, uc), gs, group = grp)
fg1 <- crr(gt, gs, cbind(x = xc, g1 = as.numeric(grp == 1), g2 = as.numeric(grp == 2)), gtol = 1e-12)
fg2 <- crr(gt, gs, cbind(x = xc, g1 = as.numeric(grp == 1), g2 = as.numeric(grp == 2)), failcode = 2, gtol = 1e-12)
D$gray$time_untied <- pmin(u1, u2, uc)
R$gray <- list(tied = n(gtie$Tests[, 1]), untied = n(gnt$Tests[, 1]),
               fg1 = list(b = n(fg1$coef), se = n(sqrt(diag(fg1$var))), ll = fg1$loglik),
               fg2 = list(b = n(fg2$coef), se = n(sqrt(diag(fg2$var)))))

# ------------------------------------------------------------------ multiplicity & power
pv <- c(0.0001, 0.004, 0.0123, 0.019, 0.022, 0.031, 0.047, 0.32, 0.51, 0.88); D$pvals <- pv
R$padj <- lapply(c(bonferroni = "bonferroni", holm = "holm", hochberg = "hochberg", hommel = "hommel", BH = "BH", BY = "BY"), function(m) p.adjust(pv, m))
R$power <- list(t = power.t.test(n = 20, delta = 1, sd = 1.5, strict = TRUE)$power, prop = power.prop.test(n = 50, p1 = 0.5, p2 = 0.75)$power,
                anova = power.anova.test(groups = 4, n = 5, between.var = 1, within.var = 3)$power,
                n_t = power.t.test(power = 0.8, delta = 1, sd = 1.5, strict = TRUE)$n)

out <- list(generated = format(Sys.time(), "%Y-%m-%d"), R = R.version.string,
            packages = sapply(c("survival", "MASS", "metafor", "psych", "car", "lmtest", "quantreg", "circular", "nlme", "coin"), function(p) as.character(packageVersion(p))),
            data = D, ref = R)
args <- commandArgs(trailingOnly = TRUE)
dest <- if (length(args)) args[1] else "validation/reference_r.json"
writeLines(toJSON(out, digits = NA, auto_unbox = TRUE, pretty = FALSE, matrix = "rowmajor"), dest)
cat("wrote", dest, "\n")
