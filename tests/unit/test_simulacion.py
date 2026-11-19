import copy
import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "simulacion"))
from reglas_simulacion import (PATRONES, PATRONES_PRUEBA, TODOS_LOS_PATRONES, aplicar_abuso,
                               asignar_patrones, descuentos_requeridos, elegir_empleados, mover_fecha,
                               mover_ticket, probabilidad_siembra, rng_para)

EFECTIVO = {"Amount": 0.0, "EmployeeId": 1, "Gratuity": 0.0, "IsCashDebit": False, "IsCreditCard": False,
            "IsGiftCard": False, "IsGiftCert": False, "IsNonPOS": False, "IsPettyCash": False,
            "PayCatName": "CASH", "PayCatNo": 1, "PaymentCategoryId": 1, "PosSourceId": 1}
IDS = {"MANAGER": ("MANAGER", 101), "WALKOUT": ("WALKOUT", 102), "SERVERERR": ("SERVERERR", 103),
       "EMP 50": ("EMP 50", 104)}


def ticket():
    return {
        "Id": 7, "LocationId": 3, "BusinessDate": "2026-08-14T00:00:00",
        "OpenTime": "2026-08-14T19:05:00", "CloseTime": "2026-08-14T20:01:00",
        "Discounts": [{"Amount": 5.0, "DiscountId": 9, "DiscountName": "PROMO", "EmployeeId": 50, "ManagerId": 60}],
        "ItemsSold": [
            {"EmployeeId": 50, "GrossPrice": 40.0, "SoldPrice": 36.0, "OrderTime": "2026-08-14T19:10:00",
             "Discounts": [{"Amount": 4.0}]},
            {"EmployeeId": 50, "GrossPrice": 0.0, "SoldPrice": 0.0, "OrderTime": "2026-08-14T19:10:00", "Discounts": []},
        ],
        "Tax": [{"Amount": 2.48, "TaxCategoryId": 1, "TaxCategoryName": "IVA"}],
        "Payments": [dict(EFECTIVO, Amount=39.48, Gratuity=-6.0, PayCatName="VISA", IsCreditCard=True, EmployeeId=50)],
    }


def conciliacion(t):
    d = lambda x: Decimal(str(x))
    sold = sum(d(i["SoldPrice"]) for i in t["ItemsSold"])
    disc = sum(d(x["Amount"]) for x in t["Discounts"])
    tax = sum(d(x["Amount"]) for x in t["Tax"])
    tip = -sum(d(p["Gratuity"]) for p in t["Payments"])
    paid = sum(d(p["Amount"]) for p in t["Payments"])
    return abs(paid - (sold - disc + tax + tip))


class SimulacionTests(unittest.TestCase):
    def test_mover_fecha(self):
        self.assertEqual(mover_fecha("2026-08-14T23:50:00Z", 7), "2026-08-21T23:50:00Z")
        self.assertEqual(mover_fecha("sin fecha", 7), "sin fecha")
        t = mover_ticket(ticket(), 7)
        self.assertEqual(t["BusinessDate"][:10], "2026-08-21")
        self.assertEqual(t["ItemsSold"][0]["OrderTime"][:10], "2026-08-21")

    def test_todos_los_patrones_concilian(self):
        for patron in TODOS_LOS_PATRONES:
            for semilla in range(30):
                with self.subTest(patron=patron, semilla=semilla):
                    t = ticket()
                    monto = aplicar_abuso(t, 77, patron, EFECTIVO, IDS, 60, rng_para(semilla))
                    self.assertIsNotNone(monto)
                    self.assertLessEqual(conciliacion(t), Decimal("0.05"))
                    self.assertTrue(all(p["Amount"] >= 0 for p in t["Payments"]))
                    self.assertLessEqual(monto, Decimal("31.00"))          # nunca más que la base
                    self.assertEqual(t["Discounts"][-1]["EmployeeId"], 77)
                    self.assertTrue(all(i["EmployeeId"] == 77 for i in t["ItemsSold"]))

    def test_senales_por_patron(self):
        t = ticket()
        aplicar_abuso(t, 77, "autoaprobado_4h", EFECTIVO, IDS, 60, rng_para(1))
        self.assertEqual(t["Discounts"][-1]["ManagerId"], 77)
        self.assertEqual(t["Payments"][0]["PayCatName"], "CASH")
        self.assertGreaterEqual(t["CloseTime"], "2026-08-14T23:17")
        t = ticket()
        t["OpenTime"], t["CloseTime"] = "2026-08-14T11:06", "2026-08-14T11:42"   # formato real
        aplicar_abuso(t, 77, "autoaprobado_4h", EFECTIVO, IDS, 60, rng_para(1))
        self.assertRegex(t["CloseTime"], r"^2026-08-14T1[5-7]:\d\d$")
        t = ticket()
        aplicar_abuso(t, 77, "walkout_sin_gerente", EFECTIVO, IDS, 60, rng_para(1))
        self.assertEqual(t["Discounts"][-1]["ManagerId"], 0)
        t = ticket()
        aplicar_abuso(t, 77, "sutil", EFECTIVO, IDS, 60, rng_para(1))
        self.assertEqual(t["Payments"][0]["PayCatName"], "VISA")
        self.assertEqual(t["CloseTime"], "2026-08-14T20:01:00")

    def test_misma_estructura_que_la_fuente(self):
        t = ticket()
        llaves = set(t)
        aplicar_abuso(t, 77, "efectivo_manager", EFECTIVO, IDS, 60, rng_para(3))
        self.assertEqual(set(t), llaves)
        self.assertEqual(set(t["Discounts"][-1]), set(ticket()["Discounts"][0]))
        self.assertEqual(set(t["Payments"][0]), set(EFECTIVO))

    def test_ticket_sin_base_no_se_usa(self):
        t = ticket()
        t["Discounts"][0]["Amount"] = 30.0
        original = copy.deepcopy(t)
        self.assertIsNone(aplicar_abuso(t, 77, "efectivo_manager", EFECTIVO, IDS, 60, rng_para(1)))
        self.assertEqual(t, original)
        t = ticket()
        t["Payments"] = [dict(EFECTIVO)]
        original = copy.deepcopy(t)
        self.assertIsNone(aplicar_abuso(t, 77, "sutil", EFECTIVO, IDS, 60, rng_para(1)))
        self.assertEqual(t, original)

    def test_reproducible_y_una_tienda_por_empleado(self):
        candidatos = [(e, e % 5) for e in range(1, 40)]
        a = elegir_empleados(candidatos, 4, rng_para("x"))
        self.assertEqual(a, elegir_empleados(list(reversed(candidatos)), 4, rng_para("x")))
        self.assertEqual(len({loc for _, loc in a}), 4)
        self.assertEqual([p for *_, p in asignar_patrones(a)], list(PATRONES))

    def test_cohorte_prueba(self):
        candidatos = [(e, e % 12) for e in range(1, 80)]
        base = elegir_empleados(candidatos, 4, rng_para("x"))
        usados = {loc for _, loc in base}
        prueba = elegir_empleados(candidatos, 4, rng_para("x", "prueba"), excluir_tiendas=usados)
        self.assertFalse(usados & {loc for _, loc in prueba})
        self.assertEqual([p for *_, p in asignar_patrones(prueba, "prueba")], list(PATRONES_PRUEBA))
        self.assertFalse(set(PATRONES) & set(PATRONES_PRUEBA))
        self.assertEqual(set(descuentos_requeridos()), set(IDS))
        distintos = elegir_empleados([(e, l) for e in range(8) for l in range(20)], 8, rng_para("x"))
        self.assertEqual(len({e for e, _ in distintos}), 8)
        self.assertEqual(len({l for _, l in distintos}), 8)

    def test_senales_cohorte_prueba(self):
        t = ticket()
        aplicar_abuso(t, 77, "error_servidor", EFECTIVO, IDS, 60, rng_para(1))
        self.assertEqual(t["Discounts"][-1]["DiscountName"], "SERVERERR")
        self.assertEqual(t["Payments"][0]["PayCatName"], "CASH")
        t = ticket()
        monto = aplicar_abuso(t, 77, "emp50_clientes", EFECTIVO, IDS, 60, rng_para(1))
        self.assertEqual(monto, Decimal("15.50"))                       # 50 % de la base de 31
        self.assertEqual(t["Payments"][0]["PayCatName"], "VISA")
        t = ticket()
        aplicar_abuso(t, 77, "walkout_tarjeta", EFECTIVO, IDS, 60, rng_para(1))
        self.assertEqual(t["Discounts"][-1]["ManagerId"], 0)
        self.assertTrue(t["Payments"][0]["IsCreditCard"])

    def test_frecuencia_por_patron(self):
        self.assertAlmostEqual(probabilidad_siembra("efectivo_manager", 15, 300), 0.05)
        self.assertAlmostEqual(probabilidad_siembra("goteo_manager", 15, 300), 0.0075)
        self.assertLess(probabilidad_siembra("goteo_manager", 15, 300),
                        probabilidad_siembra("error_servidor", 15, 300))


if __name__ == "__main__":
    unittest.main()
